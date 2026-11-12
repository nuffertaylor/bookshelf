import pytest

from bookshelf import hardcover_client as hc
from bookshelf import hardcover_library as lib
from tests.fakes import FakeDB, FakeHardcover
from tests.unit.test_hardcover_client import _linked_db


def _ub(book_id, title="T", authors=(("Author", "Ann"),), rating=None, isbn13="9780000000001"):
    return {
        "rating": rating, "last_read_date": "2024-01-02", "book_id": book_id,
        "edition": {"isbn_10": None, "isbn_13": isbn13},
        "book": {"id": book_id, "title": title, "release_year": 1999,
                 "contributions": [{"contribution": c, "author": {"name": n}} for c, n in authors]},
    }


def test_author_prefers_author_contribution_then_first_entry():
    book = {"contributions": [{"contribution": "Illustrator", "author": {"name": "Ill"}},
                              {"contribution": "Author", "author": {"name": "Writer"}}]}
    assert lib.author_name(book) == "Writer"
    assert lib.author_name({"contributions": [{"contribution": "Editor", "author": {"name": "Ed"}}]}) == "Ed"
    assert lib.author_name({"contributions": []}) == ""


def test_map_book_shape_rating_and_isbn_fallback():
    ub = _ub(5, rating=3.5, isbn13=None)
    ub["edition"]["isbn_10"] = "0306406152"
    mapped = lib.map_book(ub["book"], ub["edition"], ub["rating"], ub["last_read_date"])
    assert mapped["hardcover_book_id"] == 5 and "book_id" not in mapped
    assert mapped["user_rating"] == "4"      # half rounds up, Goodreads-style int string
    assert mapped["isbn13"] == "9780306406157"
    assert mapped["pubDate"] == "1999" and mapped["user_read_at"] == "2024-01-02"


def test_shelves_counts_and_lists_with_me_as_array(monkeypatch):
    fake = FakeHardcover()
    me = {"id": 1, "lists": [{"id": 456, "name": "My Favs", "books_count": 9}]}
    for sid in range(1, 6):
        me[f"s{sid}"] = {"aggregate": {"count": sid * 10}}
    fake.graphql = [(200, {"data": {"me": [me]}})]
    monkeypatch.setattr(hc, "_request", fake)
    shelves = lib.get_shelves(_linked_db(3600), "alice")
    assert shelves[2] == {"id": "status:3", "name": "Read", "count": 30}
    assert shelves[-1] == {"id": "list:456", "name": "My Favs", "count": 9}


def test_status_shelf_paginates_across_three_pages(monkeypatch):
    fake = FakeHardcover()
    page1 = [_ub(i) for i in range(500)]
    page2 = [_ub(i) for i in range(500, 1000)]
    page3 = [_ub(i) for i in range(1000, 1400)]
    fake.graphql = [(200, {"data": {"me": [{"user_books": p}]}}) for p in (page1, page2, page3)]
    monkeypatch.setattr(hc, "_request", fake)
    books = lib.get_shelf_books(_linked_db(3600), "alice", "status:3")
    assert len(books) == 1400
    assert len(fake.calls_to("/v1/graphql")) == 3
    import json
    offsets = [json.loads(c["data"])["variables"]["offset"] for c in fake.calls_to("/v1/graphql")]
    assert offsets == [0, 500, 1000]


def test_list_shelf_uses_users_own_rating(monkeypatch):
    fake = FakeHardcover()
    lb = {"book_id": 9, "edition": None, "book": _ub(9, "Nine")["book"],
          "user_books": [{"rating": 4.0, "status_id": 3, "last_read_date": "2023-05-05"}]}
    fake.graphql = [(200, {"data": {"me": [{"lists": [{"id": 456, "name": "x", "list_books": [lb]}]}]}})]
    monkeypatch.setattr(hc, "_request", fake)
    books = lib.get_shelf_books(_linked_db(3600), "alice", "list:456")
    assert books[0]["user_rating"] == "4" and books[0]["title"] == "Nine"


def test_unknown_list_and_bad_ids(monkeypatch):
    fake = FakeHardcover()
    fake.graphql = [(200, {"data": {"me": [{"lists": []}]}})]
    monkeypatch.setattr(hc, "_request", fake)
    with pytest.raises(lib.ShelfNotFound):
        lib.get_shelf_books(_linked_db(3600), "alice", "list:1")
    for bad in ("status:9", "list:abc", "nope", "status:", "status:1; drop"):
        with pytest.raises(lib.ShelfNotFound):
            lib.get_shelf_books(FakeDB(), "alice", bad)


def test_429_propagates(monkeypatch):
    fake = FakeHardcover()
    fake.graphql = [(429, {})]
    monkeypatch.setattr(hc, "_request", fake)
    with pytest.raises(hc.HardcoverRateLimited):
        lib.get_shelf_books(_linked_db(3600), "alice", "status:3")
