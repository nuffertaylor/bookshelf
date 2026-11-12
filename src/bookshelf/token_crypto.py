"""Encrypt/decrypt stored Hardcover tokens with AWS KMS.

The username is bound in as the EncryptionContext, so a ciphertext copied to another user's row
will not decrypt. Tokens are far below KMS's 4 KB direct-encrypt limit.

Env: KMS_KEY_ID (key id, ARN or alias), KMS_ENDPOINT_URL (optional; LocalStack in local dev).
"""
import base64
import os

_kms = None


def _client():
    global _kms
    if _kms is None:
        import boto3
        endpoint = os.getenv("KMS_ENDPOINT_URL") or None
        _kms = boto3.client("kms", endpoint_url=endpoint)
    return _kms


def _key_id():
    key_id = os.getenv("KMS_KEY_ID")
    if not key_id:
        raise RuntimeError("KMS_KEY_ID is not configured")
    return key_id


def encrypt(username, plaintext):
    """Returns a base64 string safe to store in a text column."""
    resp = _client().encrypt(
        KeyId=_key_id(),
        Plaintext=plaintext.encode("utf-8"),
        EncryptionContext={"username": username},
    )
    return base64.b64encode(resp["CiphertextBlob"]).decode("ascii")


def decrypt(username, blob):
    resp = _client().decrypt(
        CiphertextBlob=base64.b64decode(blob),
        KeyId=_key_id(),
        EncryptionContext={"username": username},
    )
    return resp["Plaintext"].decode("utf-8")
