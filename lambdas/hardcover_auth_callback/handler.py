import os
import time

from bookshelf import hardcover_client, token_crypto
from bookshelf.auth import mint_session
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.hardcover_accounts import AccountCreationError, create_account
from bookshelf.http import http_result, parse_event

_db = None

_TRY_AGAIN = "Hardcover sign-in failed, please try again."


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    """POST /auth/hardcover/callback  {"code", "state", "iss"} (or {"error", "error_description", "state"}).
    login mode -> {username, authtoken, goodreads_id, hardcover_username, is_new_account}
    link mode  -> {linked: true, hardcover_username}"""
    try:
        event = parse_event(event)
    except ValueError:
        return http_result(400, {"error": "request body must be JSON"})
    if not isinstance(event, dict):
        return http_result(400, {"error": "request body must be a JSON object"})

    db = _get_db()
    now = int(time.time())
    state = event.get("state")
    if not isinstance(state, str) or not state:
        return http_result(400, {"error": "state is required"})

    if event.get("error"):
        # The user denied consent (or Hardcover reported an error). Burn the state.
        db.consume_oauth_state(state, now)
        return http_result(400, {"error": "Hardcover sign-in was cancelled or denied."})

    if event.get("iss") != hardcover_client.ISSUER:
        return http_result(400, {"error": "unexpected issuer in the Hardcover response"})
    code = event.get("code")
    if not isinstance(code, str) or not code:
        return http_result(400, {"error": "code is required"})

    # Atomic UPDATE ... RETURNING: unknown, expired and replayed states all come back as None.
    pending = db.consume_oauth_state(state, now)
    if not pending:
        return http_result(400, {"error": "This sign-in link expired or was already used. Please try again."})

    try:
        tokens = hardcover_client.exchange_code(code, pending["code_verifier"])
        if not tokens.get("refresh_token"):
            raise hardcover_client.HardcoverError("token response had no refresh_token")
        me = hardcover_client.fetch_me(tokens["access_token"])
    except hardcover_client.HardcoverError as e:
        print("hardcover callback failed: status=" + str(e.status) + " error=" + str(e.error))
        # 4xx from the token endpoint (e.g. redirect_uri mismatch, bad code) is not retryable as-is.
        status = 400 if e.status is not None and 400 <= e.status < 500 else 502
        return http_result(status, {"error": _TRY_AGAIN})

    try:
        hardcover_id = int(me["id"])
    except (TypeError, ValueError):
        return http_result(502, {"error": _TRY_AGAIN})
    hardcover_username = str(me.get("username") or "")

    if pending["mode"] == "link":
        return _handle_link(db, pending["username"], hardcover_id, hardcover_username, tokens, now)
    return _handle_login(db, hardcover_id, hardcover_username, me.get("email"), tokens, now)


def _store_connection(db, username, hardcover_id, hardcover_username, tokens, now):
    return db.upsert_hardcover_connection(
        username,
        hardcover_id,
        hardcover_username,
        token_crypto.encrypt(username, tokens["access_token"]),
        token_crypto.encrypt(username, tokens["refresh_token"]),
        hardcover_client.token_expiry(tokens, now),
        tokens.get("scope") or hardcover_client.USER_SCOPE,
    )


def _login_response(session, hardcover_username, is_new):
    return http_result(200, {
        "username": session["username"],
        "authtoken": session["authtoken"],
        "goodreads_id": session.get("goodreads_id"),
        "hardcover_username": hardcover_username,
        "is_new_account": is_new,
    })


def _handle_login(db, hardcover_id, hardcover_username, email, tokens, now):
    user = db.get_user_by_hardcover_id(hardcover_id)
    if user:
        if user.get("banned"):
            return http_result(403, {"error": "This account is not permitted to sign in."})
        # `username` stays frozen; only the display name and tokens refresh.
        if not _store_connection(db, user["username"], hardcover_id, hardcover_username, tokens, now):
            return http_result(500, {"error": _TRY_AGAIN})
        session = mint_session(db, user["username"])
        if not session:
            return http_result(500, {"error": _TRY_AGAIN})
        return _login_response(session, hardcover_username, False)

    # Never match an existing account by username or email: a new Hardcover identity gets a new account.
    try:
        created = create_account(db, hardcover_username, email)
    except AccountCreationError:
        return http_result(500, {"error": "Could not create an account, please try again."})
    username = created["username"]
    if not _store_connection(db, username, hardcover_id, hardcover_username, tokens, now):
        # Lost a race with a concurrent first sign-in for the same Hardcover user: undo our account
        # and, if that sign-in created the connection, log in to it instead.
        db.delete_user(username)
        user = db.get_user_by_hardcover_id(hardcover_id)
        if user and not user.get("banned"):
            session = mint_session(db, user["username"])
            if session:
                return _login_response(session, hardcover_username, False)
        return http_result(500, {"error": _TRY_AGAIN})
    session = {"username": username, "authtoken": created["authtoken"], "goodreads_id": None}
    return _login_response(session, hardcover_username, True)


def _handle_link(db, username, hardcover_id, hardcover_username, tokens, now):
    user = db.get_user(username) if username else None
    if not user:
        return http_result(400, {"error": "The account to link no longer exists."})
    if user.get("banned"):
        return http_result(403, {"error": "This account is not permitted to link Hardcover."})
    owner = db.get_user_by_hardcover_id(hardcover_id)
    if owner and owner["username"] != username:
        return http_result(409, {"error": "hardcover_already_linked"})
    current = db.get_hardcover_connection(username)
    if current and current["hardcover_id"] != hardcover_id:
        return http_result(409, {"error": "account_linked_to_different_hardcover"})
    if not _store_connection(db, username, hardcover_id, hardcover_username, tokens, now):
        # Most likely the UNIQUE(hardcover_id) constraint, lost to a concurrent link.
        return http_result(409, {"error": "hardcover_already_linked"})
    return http_result(200, {"linked": True, "hardcover_username": hardcover_username})
