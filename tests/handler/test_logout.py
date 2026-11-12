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


def test_logout_revokes_the_hardcover_refresh_token(setup):
    db, fake = setup
    db.upsert_hardcover_connection("alice", 1, "a", token_crypto.encrypt("alice", "at"),
                                   token_crypto.encrypt("alice", "hc_rt_live"), 0, "s")
    assert call(load("logout"), db, {"username": "alice", "authtoken": "tok"})[0] == 200
    calls = fake.calls_to("/oauth2/revoke")
    assert len(calls) == 1 and b"hc_rt_live" in calls[0]["data"]
    assert db.connections["alice"]["needs_reauth"] is True


def test_revoke_failure_does_not_fail_logout(setup, monkeypatch):
    db, _ = setup
    db.upsert_hardcover_connection("alice", 1, "a", token_crypto.encrypt("alice", "at"),
                                   token_crypto.encrypt("alice", "rt"), 0, "s")

    def boom(*a, **k):
        raise hc.HardcoverError("down")

    monkeypatch.setattr(hc, "_request", boom)
    assert call(load("logout"), db, {"username": "alice", "authtoken": "tok"})[0] == 200
    assert not db.validate_username_authtoken("alice", "tok")
