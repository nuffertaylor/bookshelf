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


# ---- search_books (contribute flow) ----------------------------------------------------------

def _hit(id="123", **over):
    doc = {"id": id, "title": "Project Hail Mary", "subtitle": "A Novel", "author_names": ["Andy Weir"],
           "contributions": [{"contribution": "Author", "author": {"name": "Andy Weir"}}],
           "release_year": 2021, "isbns": ["0593135202", "9780593135204"]}
    doc.update(over)
    return {"document": doc}


def _search_db(monkeypatch, results, status=200):
    fake = FakeHardcover()
    fake.graphql = [(status, {"data": {"search": {"results": results}}})]
    monkeypatch.setattr(hc, "_request", fake)
    db = _linked_db(3600)
    db.connections["alice"]["scopes"] = "read:library read:catalog"
    return db, fake


def test_search_normalizes_hit(monkeypatch):
    db, fake = _search_db(monkeypatch, {"hits": [_hit()], "found": 1})
    db.spines = [{"submitter": "alice", "hardcover_book_id": 123}]
    assert lib.search_books(db, "alice", "  project hail mary ") == [{
        "hardcover_book_id": 123, "title": "Project Hail Mary", "subtitle": "A Novel", "author": "Andy Weir",
        "pubDate": "2021", "isbn": "0593135202", "isbn13": "9780593135204", "already_uploaded": True}]
    import json
    sent = json.loads(fake.calls_to("/v1/graphql")[0]["data"])
    assert sent["variables"] == {"q": "project hail mary", "n": 10}


def test_search_results_as_json_string(monkeypatch):
    import json
    db, _ = _search_db(monkeypatch, json.dumps({"hits": [_hit()]}))
    assert [r["hardcover_book_id"] for r in lib.search_books(db, "alice", "hail mary")] == [123]


def test_search_isbn10_only_converts_and_x_check_digit(monkeypatch):
    db, _ = _search_db(monkeypatch, {"hits": [_hit(isbns=["0593135202"]), _hit(id="2", isbns=["043942089X"]), _hit(id="3", isbns=None)]})
    r = lib.search_books(db, "alice", "hail mary")
    assert (r[0]["isbn"], r[0]["isbn13"]) == ("0593135202", "9780593135204")
    assert r[1]["isbn"] == "043942089X" and r[1]["isbn13"] == ""  # X check digit: no conversion
    assert (r[2]["isbn"], r[2]["isbn13"]) == ("", "")


def test_search_author_fallback_missing_subtitle_and_year(monkeypatch):
    db, _ = _search_db(monkeypatch, {"hits": [
        _hit(contributions=None), _hit(id="2", contributions=None, author_names=None, subtitle=None, release_year=None)]})
    r = lib.search_books(db, "alice", "hail mary")
    assert r[0]["author"] == "Andy Weir"
    assert r[1]["author"] == "" and r[1]["subtitle"] == "" and r[1]["pubDate"] == ""


def test_search_skips_non_integer_ids(monkeypatch):
    db, _ = _search_db(monkeypatch, {"hits": [_hit(id="abc"), _hit(id=None), _hit(id="7"), "junk", {}]})
    assert [r["hardcover_book_id"] for r in lib.search_books(db, "alice", "hail mary")] == [7]


@pytest.mark.parametrize("results", [None, {}, {"hits": None}, {"hits": "x"}, [], "not json", 5])
def test_search_malformed_results_are_empty(monkeypatch, results):
    db, _ = _search_db(monkeypatch, results)
    assert lib.search_books(db, "alice", "hail mary") == []


@pytest.mark.parametrize("query", [None, 5, "", "ab", "  a ", "x" * 201])
def test_search_query_validation(monkeypatch, query):
    db, fake = _search_db(monkeypatch, {"hits": []})
    with pytest.raises(ValueError):
        lib.search_books(db, "alice", query)
    assert fake.calls == []


def test_search_query_length_bounds_ok(monkeypatch):
    db, _ = _search_db(monkeypatch, {"hits": []})
    assert lib.search_books(db, "alice", "abc") == []
    assert lib.search_books(db, "alice", "x" * 200) == []


@pytest.mark.parametrize("bad", ["1_0", "+5", "-5", "5.0", " ", "\u0663\u0664", "\uff11\uff12", "9223372036854775808",
                                 "1" * 40, True, 1.5, [], {}])
def test_search_skips_unsafe_ids(monkeypatch, bad):
    db, _ = _search_db(monkeypatch, {"hits": [_hit(id=bad), _hit(id="8")]})
    assert [r["hardcover_book_id"] for r in lib.search_books(db, "alice", "hail mary")] == [8]


def test_search_accepts_int_id_and_max_int64(monkeypatch):
    db, _ = _search_db(monkeypatch, {"hits": [_hit(id=5), _hit(id="9223372036854775807")]})
    assert [r["hardcover_book_id"] for r in lib.search_books(db, "alice", "hail mary")] == [5, 2**63 - 1]


@pytest.mark.parametrize("year,expected", [
    (1965, "1965"), (1965.0, "1965"), ("1965", "1965"), ("1965.0", "1965"), (" 1965 ", "1965"),
    (1965.5, ""), ("abc", ""), ("", ""), (None, ""), (0, ""), (True, ""), ([], ""), (float("nan"), ""),
    (float("inf"), ""), ("19650", ""), (-5, "")])
def test_search_pubdate_normalization(monkeypatch, year, expected):
    db, _ = _search_db(monkeypatch, {"hits": [_hit(release_year=year)]})
    assert lib.search_books(db, "alice", "hail mary")[0]["pubDate"] == expected


def test_search_title_subtitle_only_strings(monkeypatch):
    db, _ = _search_db(monkeypatch, {"hits": [
        _hit(title=42, subtitle={"a": 1}), _hit(id="2", title=None, subtitle=3.5), _hit(id="3", title="T", subtitle="S")]})
    r = lib.search_books(db, "alice", "hail mary")
    assert [(x["title"], x["subtitle"]) for x in r] == [("", ""), ("", ""), ("T", "S")]
