import json
import os

import pytest

os.environ.setdefault("SKIP_SSL_CERT", "true")
os.environ.setdefault("DATABASE_URL", "postgresql://localhost/test")


class FakeKms:
    """Stand-in for the boto3 KMS client: binds the EncryptionContext like the real thing."""

    def encrypt(self, KeyId, Plaintext, EncryptionContext):
        blob = json.dumps({"ctx": EncryptionContext, "pt": Plaintext.decode()[::-1]}).encode()
        return {"CiphertextBlob": blob}

    def decrypt(self, CiphertextBlob, KeyId, EncryptionContext):
        doc = json.loads(CiphertextBlob)
        if doc["ctx"] != EncryptionContext:
            raise RuntimeError("InvalidCiphertextException")
        return {"Plaintext": doc["pt"][::-1].encode()}


@pytest.fixture(autouse=True)
def hardcover_env(monkeypatch):
    """Fake config, fake KMS, and a network guard so no test can reach Hardcover or AWS."""
    from bookshelf import hardcover_client, token_crypto

    monkeypatch.setenv("HARDCOVER_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HARDCOVER_CLIENT_SECRET", "not-a-real-secret")
    monkeypatch.setenv("HARDCOVER_REDIRECT_URI", "http://localhost:3000/oauth/callback")
    monkeypatch.setenv("KMS_KEY_ID", "test-key")
    monkeypatch.setattr(hardcover_client, "_client_secret", None)
    monkeypatch.setattr(hardcover_client, "_endpoints", dict(hardcover_client.DEFAULT_ENDPOINTS))
    monkeypatch.setattr(token_crypto, "_kms", FakeKms())

    def no_network(*args, **kwargs):
        raise AssertionError("test attempted a real network call; patch hardcover_client._request")

    monkeypatch.setattr(hardcover_client, "_request", no_network)
