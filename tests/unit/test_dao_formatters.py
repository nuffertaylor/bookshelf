import os
import uuid
from unittest.mock import patch, MagicMock

os.environ["SKIP_SSL_CERT"] = "true"


@patch("bookshelf.dao.cockroachdb_dao.psycopg2.connect")
def test_format_book_tuple(mock_connect):
    mock_connect.return_value = MagicMock()
    from bookshelf.dao.cockroachdb_dao import CockroachDAO
    dao = CockroachDAO("postgresql://localhost/test")
    uid = uuid.uuid4()
    book_tuple = (uid, 123, "My Book", "Author Name", "9x6x1", "#ff0000",
                  "mybook.jpg", "fiction", "0123456789", "9780123456789", "2020", "testuser", 4, False)
    result = dao.format_book_tuple(book_tuple)
    assert result["title"] == "My Book"
    assert result["author"] == "Author Name"
    assert result["upload_id"] == uid


@patch("bookshelf.dao.cockroachdb_dao.psycopg2.connect")
def test_format_shelf_bg_tuple(mock_connect):
    mock_connect.return_value = MagicMock()
    from bookshelf.dao.cockroachdb_dao import CockroachDAO
    dao = CockroachDAO("postgresql://localhost/test")
    uid = uuid.uuid4()
    bg_tuple = (uid, "testuser", "bg.jpg", 36, 1440, [100, 200], 50, 12345, "My Shelf")
    result = dao.format_shelf_bg_tuple(bg_tuple)
    assert result["submitter"] == "testuser"
    assert result["filename"] == "bg.jpg"


@patch("bookshelf.dao.cockroachdb_dao.psycopg2.connect")
def test_format_book_tuple_hardcover_id_is_last_column(mock_connect):
    mock_connect.return_value = MagicMock()
    from bookshelf.dao.cockroachdb_dao import CockroachDAO
    dao = CockroachDAO("postgresql://localhost/test")
    base = (uuid.uuid4(), None, "My Book", "A", "9x6x1", "#ff0000", "f.jpg", "g", "i", "i13", "2020", "u", 4, False, 1700000000)
    assert dao.format_book_tuple(base)["hardcover_book_id"] is None  # row from before the column existed
    result = dao.format_book_tuple(base + (777,))
    assert result["hardcover_book_id"] == 777 and result["book_id"] is None


@patch("bookshelf.dao.cockroachdb_dao.psycopg2.connect")
def test_format_unfound_tuple_hardcover_id(mock_connect):
    mock_connect.return_value = MagicMock()
    from bookshelf.dao.cockroachdb_dao import CockroachDAO
    dao = CockroachDAO("postgresql://localhost/test")
    row = (uuid.uuid4(), None, "T", "A", "i", "i13", "2020", "owner", False, 1700000000, 55)
    assert dao.format_unfound_to_upload_tuple(row)["hardcover_book_id"] == 55
