import os
import time

from bookshelf import hardcover_client, token_crypto
from bookshelf.auth import gen_authtoken
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.http import http_result, parse_event

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    """POST /logout {"username", "authtoken"}: invalidate the site session server-side, then
    best-effort revoke the user's Hardcover tokens (so their Authorized apps page stays clean)."""
    try:
        event = parse_event(event)
    except ValueError:
        return http_result(400, {"error": "request body must be JSON"})
    if not isinstance(event, dict):
        return http_result(400, {"error": "request body must be a JSON object"})

    username = event.get("username")
    authtoken = event.get("authtoken")
    if not isinstance(username, str) or not isinstance(authtoken, str) or not username or not authtoken:
        return http_result(403, {"error": "invalid or expired session"})
    db = _get_db()
    if not db.validate_username_authtoken(username, authtoken):
        return http_result(403, {"error": "invalid or expired session"})

    # Replace the token and expire it, so the old pair can never validate again.
    if not db.update_user_authtoken(username, gen_authtoken(), int(time.time()) - 1):
        return http_result(500, {"error": "could not log out, please try again"})

    _revoke_hardcover(db, username)
    return http_result(200, {"logged_out": True})


def _revoke_hardcover(db, username):
    """Never raises: the session is already dead, and a failed revoke must not look like a failed logout."""
    try:
        with db.transaction() as cur:
            # Lock so we don't race a refresh that is about to rotate the token we are revoking.
            conn = db.lock_hardcover_connection(cur, username)
            if not conn or conn["needs_reauth"]:
                return
            refresh_token = token_crypto.decrypt(username, conn["refresh_token_enc"])
            hardcover_client.revoke(refresh_token)
            # Whether or not the revoke call succeeded, do not keep using these tokens.
            db.set_hardcover_needs_reauth(cur, username)
    except Exception as e:  # noqa: BLE001
        print("hardcover revoke on logout failed: " + type(e).__name__)
