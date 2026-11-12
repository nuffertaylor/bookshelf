import base64
import hashlib
import json
import time
import urllib.parse

import pytest

from bookshelf import hardcover_client as hc
from tests.fakes import FakeDB, FakeHardcover, token_response


def test_pkce_challenge_is_unpadded_base64url_sha256():
    verifier, challenge = hc.generate_pkce()
    assert 43 <= len(verifier) <= 128
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected
    assert "=" not in challenge


def test_state_values_are_unique():
    assert hc.generate_state() != hc.generate_state()


def test_authorize_url():
    url = hc.build_authorize_url("st", "chal")
    parsed = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(parsed.query))
    assert parsed.netloc == "hardcover.app" and parsed.path == "/oauth2/authorize"
    assert q["response_type"] == "code" and q["code_challenge_method"] == "S256"
    assert q["state"] == "st" and q["code_challenge"] == "chal"
    assert q["client_id"] == "test-client-id"
    assert q["redirect_uri"] == "http://localhost:3000/oauth/callback"
    assert q["scope"] == "read:me:email read:library read:lists openid"


def test_discovery_falls_back_and_rejects_foreign_hosts(monkeypatch):
    monkeypatch.setattr(hc, "_endpoints", None)
    doc = {"issuer": hc.ISSUER, "token_endpoint": "https://evil.example/token",
           "revocation_endpoint": "https://api.hardcover.app/oauth2/revoke2"}
    monkeypatch.setattr(hc, "_request", lambda *a, **k: (200, {}, json.dumps(doc)))
    ep = hc.get_endpoints()
    assert ep["token_endpoint"] == hc.DEFAULT_ENDPOINTS["token_endpoint"]
    assert ep["revocation_endpoint"].endswith("/revoke2")


def test_discovery_failure_uses_defaults(monkeypatch):
    def boom(*a, **k):
        raise hc.HardcoverError("down")
    monkeypatch.setattr(hc, "_request", boom)
    monkeypatch.setattr(hc, "_endpoints", None)
    assert hc.get_endpoints() == hc.DEFAULT_ENDPOINTS


def test_exchange_code_sends_basic_auth_pkce_and_redirect(monkeypatch):
    fake = FakeHardcover()
    fake.token = [(200, token_response())]
    monkeypatch.setattr(hc, "_request", fake)
    hc.exchange_code("the-code", "the-verifier")
    call = fake.calls_to("/oauth2/token")[0]
    form = dict(urllib.parse.parse_qsl(call["data"].decode()))
    assert form == {"grant_type": "authorization_code", "code": "the-code",
                    "redirect_uri": "http://localhost:3000/oauth/callback", "code_verifier": "the-verifier"}
    expected = "Basic " + base64.b64encode(b"test-client-id:not-a-real-secret").decode()
    assert call["headers"]["Authorization"] == expected


def test_exchange_code_400_raises_with_error(monkeypatch):
    fake = FakeHardcover()
    fake.token = [(400, {"error": "invalid_grant"})]
    monkeypatch.setattr(hc, "_request", fake)
    with pytest.raises(hc.HardcoverError) as e:
        hc.exchange_code("c", "v")
    assert e.value.status == 400 and e.value.error == "invalid_grant"


def test_first_me_handles_array_object_and_empty():
    assert hc.first_me({"me": [{"id": 1}]}) == {"id": 1}
    assert hc.first_me({"me": {"id": 1}}) == {"id": 1}
    assert hc.first_me({"me": []}) is None
    assert hc.first_me({}) is None


def test_fetch_me_empty_array_raises(monkeypatch):
    fake = FakeHardcover()
    fake.graphql = [(200, {"data": {"me": []}})]
    monkeypatch.setattr(hc, "_request", fake)
    with pytest.raises(hc.HardcoverError):
        hc.fetch_me("tok")


def test_graphql_maps_401_and_429(monkeypatch):
    fake = FakeHardcover()
    monkeypatch.setattr(hc, "_request", fake)
    fake.graphql = [(401, {})]
    with pytest.raises(hc.HardcoverUnauthorized):
        hc.graphql("q", {}, "tok")
    fake.graphql = [(429, {}, {"Retry-After": "7"})]
    with pytest.raises(hc.HardcoverRateLimited) as e:
        hc.graphql("q", {}, "tok")
    assert e.value.retry_after == "7"
    fake.graphql = [(200, {"errors": [{"message": "boom"}]})]
    with pytest.raises(hc.HardcoverError, match="boom"):
        hc.graphql("q", {}, "tok")


def test_client_secret_from_secrets_manager(monkeypatch):
    monkeypatch.delenv("HARDCOVER_CLIENT_SECRET")
    monkeypatch.setenv("HARDCOVER_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:1:secret:x")
    import boto3

    class SM:
        def get_secret_value(self, SecretId):
            return {"SecretString": json.dumps({"client_secret": "from-sm"})}

    monkeypatch.setattr(boto3, "client", lambda name, **kw: SM())
    assert hc.get_client_secret() == "from-sm"


def test_client_secret_missing_is_an_error(monkeypatch):
    monkeypatch.delenv("HARDCOVER_CLIENT_SECRET")
    monkeypatch.delenv("HARDCOVER_SECRET_ARN", raising=False)
    with pytest.raises(RuntimeError):
        hc.get_client_secret()


# ---- get_valid_access_token ------------------------------------------------------------------

def _linked_db(expires_in, needs_reauth=False):
    from bookshelf import token_crypto
    db = FakeDB()
    db.add_legacy_user("alice")
    db.upsert_hardcover_connection(
        "alice", 42, "alice_hc", token_crypto.encrypt("alice", "hc_at_old"),
        token_crypto.encrypt("alice", "hc_rt_old"), int(time.time()) + expires_in, "read:library")
    db.connections["alice"]["needs_reauth"] = needs_reauth
    return db


def test_fresh_token_is_used_without_refresh(monkeypatch):
    fake = FakeHardcover()
    monkeypatch.setattr(hc, "_request", fake)
    db = _linked_db(3600)
    assert hc.get_valid_access_token(db, "alice") == "hc_at_old"
    assert fake.calls == []


def test_expired_token_refreshes_and_persists_rotated_refresh_token(monkeypatch):
    from bookshelf import token_crypto
    fake = FakeHardcover()
    fake.token = [(200, token_response(access="hc_at_new", refresh="hc_rt_new"))]
    monkeypatch.setattr(hc, "_request", fake)
    db = _linked_db(10)  # inside the 60 s skew
    assert hc.get_valid_access_token(db, "alice") == "hc_at_new"
    form = dict(urllib.parse.parse_qsl(fake.calls_to("/oauth2/token")[0]["data"].decode()))
    assert form == {"grant_type": "refresh_token", "refresh_token": "hc_rt_old"}  # no scope
    conn = db.connections["alice"]
    assert token_crypto.decrypt("alice", conn["refresh_token_enc"]) == "hc_rt_new"
    assert token_crypto.decrypt("alice", conn["access_token_enc"]) == "hc_at_new"
    assert conn["access_expires_at"] > time.time() + 600000


@pytest.mark.parametrize("failure", [(400, {"error": "invalid_grant"}), (401, {}), (503, {}), (200, {"access_token": "x"})])
def test_refresh_failure_sets_needs_reauth_and_is_never_retried(monkeypatch, failure):
    fake = FakeHardcover()
    fake.token = [failure]
    monkeypatch.setattr(hc, "_request", fake)
    db = _linked_db(10)
    with pytest.raises(hc.HardcoverReauthRequired):
        hc.get_valid_access_token(db, "alice")
    assert db.connections["alice"]["needs_reauth"] is True
    assert len(fake.calls_to("/oauth2/token")) == 1


def test_refresh_timeout_is_ambiguous_so_needs_reauth(monkeypatch):
    def timeout(*a, **k):
        raise hc.HardcoverError("network error")
    monkeypatch.setattr(hc, "_request", timeout)
    db = _linked_db(10)
    with pytest.raises(hc.HardcoverReauthRequired):
        hc.get_valid_access_token(db, "alice")
    assert db.connections["alice"]["needs_reauth"] is True


def test_needs_reauth_short_circuits(monkeypatch):
    monkeypatch.setattr(hc, "_request", FakeHardcover())
    db = _linked_db(3600, needs_reauth=True)
    with pytest.raises(hc.HardcoverReauthRequired):
        hc.get_valid_access_token(db, "alice")


def test_unlinked_user_requires_reauth():
    db = FakeDB()
    db.add_legacy_user("alice")
    with pytest.raises(hc.HardcoverReauthRequired):
        hc.get_valid_access_token(db, "alice")


def test_user_graphql_401_marks_needs_reauth(monkeypatch):
    fake = FakeHardcover()
    fake.graphql = [(401, {})]
    monkeypatch.setattr(hc, "_request", fake)
    db = _linked_db(3600)
    with pytest.raises(hc.HardcoverReauthRequired):
        hc.user_graphql(db, "alice", "q", {})
    assert db.connections["alice"]["needs_reauth"] is True
