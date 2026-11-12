import os
import time

from bookshelf import hardcover_client
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.http import http_result, parse_event

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    """POST /auth/hardcover/start  {"mode": "login"} or {"mode": "link", "username", "authtoken"}
    -> {"authorize_url", "state"}. The PKCE verifier stays server-side in oauth_states."""
    try:
        event = parse_event(event)
    except ValueError:
        return http_result(400, {"error": "request body must be JSON"})
    if not isinstance(event, dict):
        return http_result(400, {"error": "request body must be a JSON object"})

    mode = event.get("mode")
    if mode not in ("login", "link"):
        return http_result(400, {"error": "mode must be 'login' or 'link'"})
    if not hardcover_client.get_client_id() or not hardcover_client.get_redirect_uri():
        return http_result(500, {"error": "Hardcover sign-in is not configured"})

    db = _get_db()
    username = None
    if mode == "link":
        username = event.get("username")
        authtoken = event.get("authtoken")
        if not isinstance(username, str) or not isinstance(authtoken, str) or not username or not authtoken:
            return http_result(403, {"error": "username and authtoken are required to link Hardcover"})
        if not db.validate_username_authtoken(username, authtoken):
            return http_result(403, {"error": "invalid or expired session"})

    now = int(time.time())
    db.delete_expired_oauth_states(now)
    state = hardcover_client.generate_state()
    verifier, challenge = hardcover_client.generate_pkce()
    if not db.create_oauth_state(state, verifier, mode, username, now, now + hardcover_client.STATE_TTL_SECONDS):
        return http_result(500, {"error": "could not start sign-in, please try again"})
    return http_result(200, {
        "authorize_url": hardcover_client.build_authorize_url(state, challenge),
        "state": state,
    })
