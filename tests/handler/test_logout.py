import pytest

from bookshelf import hardcover_client as hc
from bookshelf import token_crypto
from tests.fakes import FakeDB, FakeHardcover
from tests.handler.helpers import call, load


@pytest.fixture
def setup(monkeypatch):
    fake = FakeHardcover()
    monkeypatch.setattr(hc, "_request", fake)
    db = FakeDB()
    db.add_legacy_user("alice", authtoken="tok")
    return db, fake


def test_logout_invalidates_the_session_server_side(setup):
    db, _ = setup
    status, _ = call(load("logout"), db, {"username": "alice", "authtoken": "tok"})
    assert status == 200
    assert not db.validate_username_authtoken("alice", "tok")


def test_logout_requires_a_valid_session(setup):
    db, _ = setup
    assert call(load("logout"), db, {"username": "alice", "authtoken": "nope"})[0] == 403
    assert db.validate_username_authtoken("alice", "tok")


def test_logout_keeps_the_hardcover_link_so_users_never_have_to_relink(setup):
    db, fake = setup
    db.upsert_hardcover_connection("alice", 1, "a", token_crypto.encrypt("alice", "at"),
                                   token_crypto.encrypt("alice", "hc_rt_live"), 0, "s")
    assert call(load("logout"), db, {"username": "alice", "authtoken": "tok"})[0] == 200
    assert fake.calls_to("/oauth2/revoke") == []          # tokens are not revoked at Hardcover
    conn = db.connections["alice"]
    assert conn["needs_reauth"] is False                   # and the connection is still usable
    assert token_crypto.decrypt("alice", conn["refresh_token_enc"]) == "hc_rt_live"
    assert not db.validate_username_authtoken("alice", "tok")


def test_logout_works_for_an_account_that_never_linked_hardcover(setup):
    db, fake = setup
    assert call(load("logout"), db, {"username": "alice", "authtoken": "tok"})[0] == 200
    assert fake.calls_to("/oauth2/revoke") == []
    assert not db.validate_username_authtoken("alice", "tok")
