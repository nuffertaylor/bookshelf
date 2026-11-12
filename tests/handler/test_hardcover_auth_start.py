import time
import urllib.parse

from bookshelf import hardcover_client as hc
from tests.fakes import FakeDB
from tests.handler.helpers import call, load


def _db():
    db = FakeDB()
    db.add_legacy_user("alice", password="pw", authtoken="good-token")
    return db


def test_login_mode_returns_url_and_stores_verifier():
    db = _db()
    status, body = call(load("hardcover_auth_start"), db, {"mode": "login"})
    assert status == 200
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(body["authorize_url"]).query))
    assert q["state"] == body["state"]
    row = db.states[body["state"]]
    assert row["mode"] == "login" and row["username"] is None
    assert hc.code_challenge(row["code_verifier"]) == q["code_challenge"]
    assert 590 <= row["expires_at"] - time.time() <= 601
    assert "code_verifier" not in body and row["code_verifier"] not in body["authorize_url"]


def test_link_mode_requires_a_valid_session():
    db = _db()
    h = load("hardcover_auth_start")
    assert call(h, db, {"mode": "link"})[0] == 403
    assert call(h, db, {"mode": "link", "username": "alice", "authtoken": "wrong"})[0] == 403
    assert db.states == {}


def test_link_mode_binds_state_to_the_authenticated_account():
    db = _db()
    status, body = call(load("hardcover_auth_start"), db, {"mode": "link", "username": "alice", "authtoken": "good-token"})
    assert status == 200
    assert db.states[body["state"]]["username"] == "alice" and db.states[body["state"]]["mode"] == "link"


def test_invalid_mode_and_bad_body():
    h = load("hardcover_auth_start")
    assert call(h, _db(), {"mode": "nope"})[0] == 400
    assert call(h, _db(), {})[0] == 400


def test_expired_states_are_cleaned_up():
    db = _db()
    db.create_oauth_state("old", "v", "login", None, 0, 1)
    call(load("hardcover_auth_start"), db, {"mode": "login"})
    assert "old" not in db.states


def test_unconfigured_client_id_is_a_500(monkeypatch):
    monkeypatch.setenv("HARDCOVER_CLIENT_ID", "")
    assert call(load("hardcover_auth_start"), _db(), {"mode": "login"})[0] == 500
