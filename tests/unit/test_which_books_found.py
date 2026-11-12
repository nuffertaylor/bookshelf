from bookshelf.bookshelf import which_books_found
from tests.fakes import FakeDB


def _spine(upload_id, title, author, book_id=None, hardcover_book_id=None):
    return {"upload_id": upload_id, "title": title, "author": author, "book_id": book_id,
            "hardcover_book_id": hardcover_book_id, "fileName": upload_id + ".jpg"}


def _db(*spines):
    db = FakeDB()
    db.spines = list(spines)
    return db


def test_goodreads_behaviour_unchanged_exact_id_first():
    db = _db(_spine("a", "Dune", "Frank Herbert", book_id=2), _spine("b", "Dune", "Frank Herbert", book_id=1))
    found, unfound = which_books_found(db, [{"book_id": "1", "title": "Dune", "author": "Frank Herbert"}])
    assert unfound == []
    # Characterisation of the existing behaviour: spine_copy.update(b) stamps b's book_id on every
    # candidate, so all count as exact and DB order is preserved.
    assert [s["upload_id"] for s in found[0]] == ["a", "b"]


def test_goodreads_id_fallback_when_title_differs():
    db = _db(_spine("a", "Other Title", "X", book_id=7))
    found, unfound = which_books_found(db, [{"book_id": "7", "title": "Dune", "author": "Y"}])
    assert len(found) == 1 and not unfound


def test_hardcover_id_match_outranks_title_match():
    title_only = _spine("t", "Dune", "Frank Herbert", book_id=5)
    by_id = _spine("h", "Dune (Deluxe)", "F. Herbert", hardcover_book_id=99)
    book = {"hardcover_book_id": 99, "title": "Dune", "author": "Frank Herbert"}
    found, unfound = which_books_found(_db(title_only, by_id), [book])
    assert unfound == []
    assert [s["upload_id"] for s in found[0]] == ["h", "t"]


def test_null_id_legacy_spine_still_matches_by_title_and_author():
    legacy = _spine("l", "Dune", "Frank Herbert", book_id=5, hardcover_book_id=None)
    found, unfound = which_books_found(_db(legacy), [{"hardcover_book_id": 99, "title": "Dune", "author": "Frank Herbert"}])
    assert unfound == [] and found[0][0]["upload_id"] == "l"


def test_hardcover_book_with_no_match_is_unfound():
    book = {"hardcover_book_id": 99, "title": "Nope", "author": "Nobody"}
    found, unfound = which_books_found(_db(_spine("l", "Dune", "FH", book_id=5)), [book])
    assert found == [] and unfound == [book]


def test_null_spine_book_id_does_not_match_a_book_without_goodreads_id():
    spine = _spine("h", "Unrelated", "Z", hardcover_book_id=1)
    found, unfound = which_books_found(_db(spine), [{"hardcover_book_id": 2, "title": "Dune", "author": "A"}])
    assert found == [] and len(unfound) == 1
