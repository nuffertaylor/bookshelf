from tests.fakes import FakeDB
from tests.handler.helpers import call, load


def _db():
    db = FakeDB()
    db.add_legacy_user("alice", email="a@example.com", password="correct", authtoken="old")
    db.add_legacy_user("oauth_only")
    db.add_legacy_user("banned_guy", password="pw", banned=True)
    return db


def test_register_is_refused_with_clear_message():
    status, body = call(load("login_register"), _db(), {
        "requestType": "register", "username": "new", "password": "pw", "email": "n@example.com"})
    assert status == 403
    assert body == "New accounts are created by signing in with Hardcover."


def test_register_refused_even_with_missing_fields():
    assert call(load("login_register"), _db(), {"requestType": "register"})[0] == 403


def test_password_login_still_works_and_mints_30_day_session():
    import time

    from bookshelf.auth import SESSION_TTL_SECONDS
    db = _db()
    status, body = call(load("login_register"), db, {"requestType": "login", "username": "alice", "password": "correct"})
    assert status == 200 and body["username"] == "alice" and body["authtoken"] != "old"
    assert abs(db.users["alice"]["expiry"] - (time.time() + SESSION_TTL_SECONDS)) < 5
    assert db.validate_username_authtoken("alice", body["authtoken"])


def test_oauth_only_account_cannot_password_login_and_does_not_500():
    status, body = call(load("login_register"), _db(), {"requestType": "login", "username": "oauth_only", "password": "x"})
    assert status == 403 and body == "invalid username or password"


def test_unknown_user_and_wrong_password_give_the_same_message():
    h = load("login_register")
    unknown = call(h, _db(), {"requestType": "login", "username": "nobody", "password": "x"})
    wrong = call(h, _db(), {"requestType": "login", "username": "alice", "password": "nope"})
    assert unknown == wrong and unknown[0] == 403


def test_banned_user_cannot_password_login():
    status, body = call(load("login_register"), _db(), {"requestType": "login", "username": "banned_guy", "password": "pw"})
    assert status == 403 and body != "invalid username or password"


def test_non_string_credentials_do_not_500():
    h = load("login_register")
    assert call(h, _db(), {"requestType": "login", "username": "alice", "password": 123})[0] == 403
