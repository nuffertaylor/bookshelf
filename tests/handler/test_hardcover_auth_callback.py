import time

import pytest

from bookshelf import hardcover_client as hc
from bookshelf import token_crypto
from tests.fakes import FakeDB, FakeHardcover, token_response
from tests.handler.helpers import call, load

ISS = "https://api.hardcover.app"


@pytest.fixture
def env(monkeypatch):
    fake = FakeHardcover()
    fake.token = [(200, token_response())]
    fake.graphql = [(200, {"data": {"me": [{"id": 190495, "username": "reader", "name": "Reader", "email": "r@example.com"}]}})]
    monkeypatch.setattr(hc, "_request", fake)
    return {"db": FakeDB(), "fake": fake, "h": load("hardcover_auth_callback")}


def _state(db, mode="login", username=None, ttl=600, state="st1"):
    now = int(time.time())
    db.create_oauth_state(state, "verifier-123", mode, username, now, now + ttl)
    return state


def _cb(env, **over):
    payload = {"code": "abc", "state": "st1", "iss": ISS}
    payload.update(over)
    return call(env["h"], env["db"], payload)


def test_new_user_gets_account_and_session(env):
    _state(env["db"])
    status, body = _cb(env)
    assert status == 200
    assert body["username"] == "reader" and body["is_new_account"] is True
    assert body["hardcover_username"] == "reader" and body["authtoken"]
    db = env["db"]
    assert db.validate_username_authtoken("reader", body["authtoken"])
    assert db.users["reader"]["hashedPassword"] is None
    assert db.users["reader"]["email"] == "r@example.com"
    conn = db.connections["reader"]
    assert conn["hardcover_id"] == 190495
    assert "hc_at_new" not in conn["access_token_enc"] and token_crypto.decrypt("reader", conn["refresh_token_enc"]) == "hc_rt_new"
    # code exchange used the stored verifier
    assert b"verifier-123" in env["fake"].calls_to("/oauth2/token")[0]["data"]


def test_never_auto_links_to_legacy_account_with_same_name_or_email(env):
    env["db"].add_legacy_user("reader", email="r@example.com", password="pw")
    _state(env["db"])
    status, body = _cb(env)
    assert status == 200 and body["username"] == "reader-2" and body["is_new_account"] is True
    assert env["db"].users["reader-2"]["email"] is None   # already used by the legacy account
    assert "reader" not in env["db"].connections


def test_existing_connection_logs_in_and_username_stays_frozen(env):
    db = env["db"]
    db.add_legacy_user("oldname", password="pw")
    db.upsert_hardcover_connection("oldname", 190495, "previous_hc_name", "x", "y", 0, "s")
    _state(db)
    status, body = _cb(env)
    assert status == 200 and body["username"] == "oldname" and body["is_new_account"] is False
    assert db.connections["oldname"]["hardcover_username"] == "reader"
    assert "reader" not in db.users


def test_banned_user_is_rejected(env):
    db = env["db"]
    db.add_legacy_user("bad", banned=True)
    db.upsert_hardcover_connection("bad", 190495, "reader", "x", "y", 0, "s")
    _state(db)
    status, _ = _cb(env)
    assert status == 403


def test_bad_state(env):
    assert _cb(env, state="never-issued")[0] == 400


def test_reused_state_fails_second_time(env):
    _state(env["db"])
    assert _cb(env)[0] == 200
    assert _cb(env)[0] == 400


def test_expired_state(env):
    _state(env["db"], ttl=-5)
    assert _cb(env)[0] == 400
    assert env["fake"].calls == []


def test_wrong_issuer_is_rejected_before_any_network_call(env):
    _state(env["db"])
    assert _cb(env, iss="https://evil.example")[0] == 400
    assert _cb(env, iss=None)[0] == 400
    assert env["fake"].calls == []


def test_access_denied_burns_the_state(env):
    _state(env["db"])
    status, body = call(env["h"], env["db"], {"error": "access_denied", "error_description": "no", "state": "st1"})
    assert status == 400 and "denied" in body["error"].lower()
    assert _cb(env)[0] == 400  # state already consumed
    assert env["fake"].calls == []


def test_token_endpoint_400_redirect_mismatch(env):
    env["fake"].token = [(400, {"error": "invalid_grant", "error_description": "redirect_uri mismatch"})]
    _state(env["db"])
    status, body = _cb(env)
    assert status == 400 and "redirect" not in body["error"]  # no internals leaked
    assert env["db"].users == {}


def test_me_empty_array(env):
    env["fake"].graphql = [(200, {"data": {"me": []}})]
    _state(env["db"])
    assert _cb(env)[0] == 502
    assert env["db"].users == {}


def test_missing_code(env):
    _state(env["db"])
    assert _cb(env, code=None)[0] == 400


def test_lost_race_on_connection_undoes_new_account(env, monkeypatch):
    db = env["db"]
    _state(db)
    real = db.upsert_hardcover_connection

    def racing(username, hardcover_id, *rest):
        if username == "reader":  # another request linked this Hardcover id first
            db.add_legacy_user("winner")
            real("winner", hardcover_id, "reader", "x", "y", 0, "s")
            return False
        return real(username, hardcover_id, *rest)

    db.upsert_hardcover_connection = racing
    status, body = _cb(env)
    assert status == 200 and body["username"] == "winner"
    assert "reader" not in db.users


# ---- link mode -------------------------------------------------------------------------------

def test_link_success_does_not_mint_a_session(env):
    db = env["db"]
    db.add_legacy_user("alice", password="pw", authtoken="orig")
    _state(db, mode="link", username="alice")
    status, body = _cb(env)
    assert status == 200 and body == {"linked": True, "hardcover_username": "reader"}
    assert db.connections["alice"]["hardcover_id"] == 190495
    assert db.users["alice"]["authtoken"] == "orig"


def test_link_conflict_when_hardcover_id_belongs_to_another_account(env):
    db = env["db"]
    db.add_legacy_user("alice", password="pw")
    db.add_legacy_user("bob")
    db.upsert_hardcover_connection("bob", 190495, "reader", "x", "y", 0, "s")
    _state(db, mode="link", username="alice")
    status, body = _cb(env)
    assert status == 409 and body["error"] == "hardcover_already_linked"
    assert "alice" not in db.connections


def test_link_conflict_when_account_has_a_different_hardcover_id(env):
    db = env["db"]
    db.add_legacy_user("alice", password="pw")
    db.upsert_hardcover_connection("alice", 777, "someone_else", "x", "y", 0, "s")
    _state(db, mode="link", username="alice")
    assert _cb(env)[0] == 409
    assert db.connections["alice"]["hardcover_id"] == 777


def test_link_state_is_bound_to_the_account_that_started_it(env):
    db = env["db"]
    db.add_legacy_user("alice", password="pw")
    db.add_legacy_user("mallory", password="pw")
    _state(db, mode="link", username="alice")
    # Whoever completes the callback (the request carries no session), the link goes to alice only.
    status, _ = _cb(env, username="mallory", authtoken="whatever")
    assert status == 200
    assert "alice" in db.connections and "mallory" not in db.connections


def test_link_to_deleted_account_fails(env):
    _state(env["db"], mode="link", username="ghost")
    assert _cb(env)[0] == 400
