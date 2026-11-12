import importlib
import json
import os
from unittest.mock import MagicMock, patch

os.environ["SKIP_SSL_CERT"] = "true"
os.environ["DATABASE_URL"] = "postgresql://localhost/test"

HEADER = ('Book Id,Title,Author,Author l-f,Additional Authors,ISBN,ISBN13,My Rating,Publisher,Binding,'
          'Number of Pages,Year Published,Original Publication Year,Date Read,Date Added,Bookshelves,'
          'Bookshelves with positions,Exclusive Shelf,My Review,Spoiler,Private Notes,Read Count,Owned Copies\n')
CSV = (HEADER
       + '1,Book One,Author One,"One, Author",,"=""1506711987""","=""""",4,X,P,10,2019,2001,2026/10/26,2026/10/26,"fav","",read,'
         '"SECRETREVIEW",SECRETSPOILER,SECRETNOTE,1,0\n'
       + '2,Book Two,Author Two,"Two, Author",,"=""""","=""""",0,X,P,10,2019,2019,,2026/10/26,,"",to-read,,,,0,0\n')


def _load():
    import lambdas.import_gr_library_csv.handler as h
    return importlib.reload(h)


def _call(h, payload, db=None):
    event = {"body": payload if isinstance(payload, str) else json.dumps(payload)}
    with patch("bookshelf.dao.cockroachdb_dao.psycopg2.connect", return_value=MagicMock()), \
            patch.object(h, "_get_db", return_value=db or MagicMock()):
        result = h.lambda_handler(event, {})
    return result, json.loads(result["body"])["body"]


def test_lists_shelves():
    result, body = _call(_load(), {"csv": CSV})
    assert result["statusCode"] == 200
    assert {s["name"]: s["count"] for s in body["shelves"]} == {"fav": 1, "read": 1, "to-read": 1}


def test_found_unfound_shape():
    h = _load()
    found_book = [{"book_id": "1", "title": "Book One"}]
    with patch.object(h, "which_books_found", return_value=([found_book], [{"book_id": "9"}])) as m:
        result, body = _call(h, {"csv": CSV, "shelf": "read"})
    assert result["statusCode"] == 200
    assert body == {"found": [found_book], "unfound": [{"book_id": "9"}]}
    [book] = m.call_args.args[1]
    assert book["book_id"] == "1" and book["isbn13"] == "9781506711980" and book["pubDate"] == "2001"


def test_unknown_shelf_returns_404():
    h = _load()
    with patch.object(h, "which_books_found", return_value=([], [])) as matcher:
        result, body = _call(h, {"csv": CSV, "shelf": "nope"})
    assert result["statusCode"] == 404
    assert "nope" in body["error"]
    matcher.assert_not_called()


def test_review_and_notes_never_in_response():
    h = _load()
    with patch.object(h, "which_books_found", side_effect=lambda db, books: ([[b] for b in books], [])):
        for payload in ({"csv": CSV}, {"csv": CSV, "shelf": "read"}):
            result, _ = _call(h, payload)
            for secret in ("SECRETREVIEW", "SECRETSPOILER", "SECRETNOTE"):
                assert secret not in result["body"]


def test_oversized_csv_is_413():
    h = _load()
    result, body = _call(h, {"csv": "x" * (h.MAX_CSV_CHARS + 1)})
    assert result["statusCode"] == 413
    assert "error" in body


def test_too_many_rows_is_413():
    h = _load()
    with patch.object(h, "MAX_ROWS", 1):
        result, body = _call(h, {"csv": CSV})
    assert result["statusCode"] == 413
    assert "error" in body


def test_non_json_body_is_400():
    result, body = _call(_load(), "this is not json")
    assert result["statusCode"] == 400
    assert body == {"error": "request body must be JSON"}


def test_non_string_csv_is_400():
    for bad in (123, ["a"], {"a": 1}):
        result, body = _call(_load(), {"csv": bad})
        assert result["statusCode"] == 400
        assert "error" in body


def test_missing_csv_is_400():
    result, _ = _call(_load(), {"shelf": "read"})
    assert result["statusCode"] == 400


def test_non_goodreads_csv_is_400():
    result, body = _call(_load(), {"csv": "a,b\n1,2\n"})
    assert result["statusCode"] == 400
    assert "error" in body
