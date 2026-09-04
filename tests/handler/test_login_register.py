import os
from unittest.mock import patch, MagicMock

os.environ["SKIP_SSL_CERT"] = "true"
os.environ["DATABASE_URL"] = "postgresql://localhost/test"


@patch("bookshelf.dao.cockroachdb_dao.psycopg2.connect")
def test_login_unknown_user(mock_connect):
    mock_connect.return_value = MagicMock()
    import importlib
    import lambdas.login_register.handler as h
    importlib.reload(h)

    mock_db = MagicMock()
    mock_db.get_user.return_value = None
    with patch.object(h, "_get_db", return_value=mock_db):
        result = h.lambda_handler({"requestType": "login", "username": "nobody", "password": "pass"}, {})
    assert result["statusCode"] == 403


@patch("bookshelf.dao.cockroachdb_dao.psycopg2.connect")
def test_login_wrong_password(mock_connect):
    mock_connect.return_value = MagicMock()
    import importlib
    import lambdas.login_register.handler as h
    importlib.reload(h)

    from bookshelf.auth import gen_salt, hash_and_salt
    salt = gen_salt()
    mock_db = MagicMock()
    mock_db.get_user.return_value = {
        "username": "alice",
        "hashedPassword": hash_and_salt("correct_password", salt),
        "salt": salt,
    }
    with patch.object(h, "_get_db", return_value=mock_db):
        result = h.lambda_handler({"requestType": "login", "username": "alice", "password": "wrong_password"}, {})
    assert result["statusCode"] == 403


@patch("bookshelf.dao.cockroachdb_dao.psycopg2.connect")
def test_register_duplicate_username(mock_connect):
    mock_connect.return_value = MagicMock()
    import importlib
    import lambdas.login_register.handler as h
    importlib.reload(h)

    mock_db = MagicMock()
    mock_db.get_user.return_value = {"username": "alice"}
    with patch.object(h, "_get_db", return_value=mock_db):
        result = h.lambda_handler({
            "requestType": "register",
            "username": "alice",
            "password": "pass",
            "email": "alice@example.com",
        }, {})
    assert result["statusCode"] == 403
