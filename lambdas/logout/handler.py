import os
import time

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
    """POST /logout {"username", "authtoken"}: invalidate the site session server-side.

    A linked Hardcover account stays linked. Linking is a one-time step, so logging out of the site must not
    revoke the stored Hardcover tokens (that would force the user to reconnect on every login). Users who want
    to disconnect can revoke My Bookshelf under their Hardcover account's authorized apps."""
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
    return http_result(200, {"logged_out": True})
