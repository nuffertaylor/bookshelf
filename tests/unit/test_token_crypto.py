import pytest

from bookshelf import token_crypto


def test_round_trip():
    blob = token_crypto.encrypt("alice", "hc_rt_secret")
    assert "hc_rt_secret" not in blob
    assert token_crypto.decrypt("alice", blob) == "hc_rt_secret"


def test_ciphertext_does_not_decrypt_under_another_users_context():
    blob = token_crypto.encrypt("alice", "hc_rt_secret")
    with pytest.raises(RuntimeError):
        token_crypto.decrypt("bob", blob)


def test_missing_key_id_is_an_error(monkeypatch):
    monkeypatch.delenv("KMS_KEY_ID")
    with pytest.raises(RuntimeError):
        token_crypto.encrypt("alice", "x")
