import base64
import io
from unittest.mock import MagicMock, patch

from PIL import Image
from tests.handler.helpers import call, load


def _img():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _db():
    db = MagicMock()
    db.get_user.return_value = {"authtoken": "tok", "expiry": 9999999999}
    db.has_username_uploaded_book.return_value = False
    db.add_book.return_value = {"upload_id": "u-1"}
    return db


def _payload(**over):
    p = {"image": _img(), "title": "My Book!", "dimensions": "9x6x1", "username": "alice", "authtoken": "tok"}
    p.update(over)
    return p


def test_create_filename_falls_back_to_hardcover_id():
    h = load("upload_spine")
    assert "-123-" in h.create_filename("A b", 123, "png")
    assert h.create_filename("A b", None, "png", 77).startswith("Ab-hc77-")


def test_upload_requires_either_id():
    status, body = call(load("upload_spine"), _db(), _payload())
    assert status == 403 and "book_id" in body


def test_upload_rejects_non_numeric_ids():
    assert call(load("upload_spine"), _db(), _payload(hardcover_book_id="abc"))[0] == 403


def test_upload_with_only_hardcover_id():
    h = load("upload_spine")
    db = _db()
    with patch.object(h, "upload_fileobj", return_value=True) as up:
        status, body = call(h, db, _payload(hardcover_book_id="77", book_id=""))
    assert status == 200 and body["already_uploaded"] is False
    assert up.call_args.kwargs["object_name"].startswith("MyBook-hc77-")
    db.has_username_uploaded_book.assert_called_once_with("alice", None, 77)
    stored = db.add_book.call_args[0][0]
    assert stored["hardcover_book_id"] == 77 and stored["book_id"] is None


def test_upload_with_goodreads_id_is_unchanged():
    h = load("upload_spine")
    db = _db()
    with patch.object(h, "upload_fileobj", return_value=True) as up:
        status, _ = call(h, db, _payload(book_id=555))
    assert status == 200
    assert "-555-" in up.call_args.kwargs["object_name"]
    db.has_username_uploaded_book.assert_called_once_with("alice", 555, None)


def test_add_unfound_passes_hardcover_books_through():
    h = load("add_unfound_to_upload")
    db = MagicMock()
    db.validate_username_authtoken.return_value = True
    books = [{"hardcover_book_id": 5, "title": "T"}]
    status, _ = call(h, db, {"username": "alice", "authtoken": "tok", "unfound": books})
    assert status == 200
    db.add_unfound_to_uploads.assert_called_once_with(books, "alice")
    assert call(h, db, {"username": "alice", "authtoken": "tok", "unfound": "x"})[0] == 403


def test_get_unfound_returns_rows_with_hardcover_id():
    h = load("get_unfound_to_upload")
    db = MagicMock()
    db.validate_username_authtoken.return_value = True
    db.get_unfound_to_upload_by_owner.return_value = [{"book_id": None, "hardcover_book_id": 5, "title": "T"}]
    status, body = call(h, db, {"username": "alice", "authtoken": "tok"})
    assert status == 200 and body[0]["hardcover_book_id"] == 5
