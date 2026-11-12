from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def dao():
    with patch("bookshelf.dao.cockroachdb_dao.psycopg2.connect", return_value=MagicMock()):
        from bookshelf.dao.cockroachdb_dao import CockroachDAO
        d = CockroachDAO("postgresql://localhost/test")
    d.exec_statement_fetch = MagicMock(return_value=[])
    d.exec_statement = MagicMock(return_value=True)
    return d


def _sql(mock):
    args = mock.call_args[0]
    return args[0], args[1]


def test_has_username_uploaded_book_matches_whichever_id_is_present(dao):
    dao.has_username_uploaded_book("u", "12")
    sql, params = _sql(dao.exec_statement_fetch)
    assert "book_id = %s" in sql and "hardcover_book_id" not in sql and params == ("u", 12)
    dao.has_username_uploaded_book("u", None, 99)
    sql, params = _sql(dao.exec_statement_fetch)
    assert "hardcover_book_id = %s" in sql and "book_id = %s OR" not in sql and params == ("u", 99)
    dao.has_username_uploaded_book("u", 1, 2)
    sql, params = _sql(dao.exec_statement_fetch)
    assert "book_id = %s OR hardcover_book_id = %s" in sql and params == ("u", 1, 2)


def test_has_username_uploaded_book_with_no_ids_is_false_without_query(dao):
    assert dao.has_username_uploaded_book("u", None, None) is False
    dao.exec_statement_fetch.assert_not_called()


def test_has_user_saved_unfound_by_hardcover_id(dao):
    dao.exec_statement_fetch.return_value = [("row",)]
    assert dao.has_user_saved_unfound("u", None, 5) is True
    assert _sql(dao.exec_statement_fetch)[1] == ("u", 5)


def test_mark_unfound_as_uploaded_either_id(dao):
    dao.mark_unfound_as_uploaded(7)
    sql, params = _sql(dao.exec_statement)
    assert params == (True, 7) and "hardcover_book_id" not in sql
    dao.mark_unfound_as_uploaded(None, 8)
    assert _sql(dao.exec_statement)[1] == (True, 8)
    dao.exec_statement.reset_mock()
    assert dao.mark_unfound_as_uploaded() is False
    dao.exec_statement.assert_not_called()


def test_add_book_without_goodreads_id(dao):
    dao.exec_statement_fetch.return_value = [("uuid-1",)]
    book = {"hardcover_book_id": "321", "title": "T", "authorName": "A", "dimensions": "9x6x1", "fileName": "f.jpg",
            "genre": "", "isbn": "", "isbn13": "", "pubDate": "2000", "username": "u", "domColor": "#000000"}
    assert dao.add_book(book)["upload_id"] == ("uuid-1",)  # existing quirk: raw row tuple
    _, params = _sql(dao.exec_statement_fetch)
    assert params[0] is None and params[-1] == 321
    assert _sql(dao.exec_statement)[1] == (True, 321)  # marks the queue entry done via the Hardcover id


def test_add_unfound_to_upload_stores_hardcover_id(dao):
    dao.exec_statement_fetch.return_value = [("uuid-2",)]
    book = {"hardcover_book_id": 4, "title": "T", "author": "A", "isbn": "", "isbn13": None, "pubDate": ""}
    dao.add_unfound_to_upload(book, "u")
    sql, params = _sql(dao.exec_statement_fetch)
    assert "hardcover_book_id" in sql and params[0] is None and params[-1] == 4


def test_add_unfound_to_uploads_skips_known_and_id_less_books(dao):
    dao.has_user_saved_unfound = MagicMock(side_effect=[False, True])
    dao.get_book_by_ids = MagicMock(return_value=False)
    dao.add_unfound_to_upload = MagicMock()
    dao.add_unfound_to_uploads([
        {"title": "no ids"},
        {"hardcover_book_id": 1, "title": "new"},
        {"book_id": "2", "title": "already queued"},
    ], "u")
    assert [c[0][0]["title"] for c in dao.add_unfound_to_upload.call_args_list] == ["new"]


def test_spines_batch_query_includes_hardcover_ids(dao):
    dao.get_spines_batch_by_title_author([
        {"title": "A", "author": "B", "hardcover_book_id": 11},
        {"title": "C", "author": "D", "book_id": "3"},
    ])
    sql, params = _sql(dao.exec_statement_fetch)
    assert "book_id IN (%s)" in sql and "hardcover_book_id IN (%s)" in sql
    assert params[-2:] == ("3", 11) or list(params[-2:]) == ["3", 11]


def test_consume_oauth_state_is_one_atomic_update(dao):
    dao.exec_statement_fetch.return_value = [("verifier", "login", None)]
    assert dao.consume_oauth_state("st", 100) == {"code_verifier": "verifier", "mode": "login", "username": None}
    sql, params = _sql(dao.exec_statement_fetch)
    assert sql.strip().startswith("UPDATE oauth_states") and "RETURNING" in sql and "used = false" in sql
    assert params == ("st", 100)
    dao.exec_statement_fetch.return_value = []
    assert dao.consume_oauth_state("st", 100) is None


def test_username_taken_is_case_insensitive_and_raises_on_db_error(dao):
    dao.exec_statement_fetch.return_value = [(1,)]
    assert dao.username_taken("Alice") is True
    assert "LOWER(username) = LOWER(%s)" in _sql(dao.exec_statement_fetch)[0]
    dao.exec_statement_fetch.return_value = False
    with pytest.raises(RuntimeError):
        dao.username_taken("Alice")


def test_validate_username_authtoken_rejects_banned(dao):
    import time
    user = {"authtoken": "t", "expiry": int(time.time()) + 100, "banned": True}
    dao.get_user = MagicMock(return_value=user)
    assert dao.validate_username_authtoken("u", "t") is False
    user["banned"] = False
    assert dao.validate_username_authtoken("u", "t") is True


def test_transaction_commits_once_and_rolls_back_on_error(dao):
    with dao.transaction() as cur:
        assert cur is dao.conn.cursor.return_value
    dao.conn.commit.assert_called_once()
    dao.conn.commit.reset_mock()
    with pytest.raises(ValueError), dao.transaction():
        raise ValueError("boom")
    dao.conn.rollback.assert_called_once()
    dao.conn.commit.assert_not_called()
