import os

from bookshelf.auth import hash_and_salt, mint_session
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.http import http_result, parse_event

_db = None

REGISTER_DISABLED = "New accounts are created by signing in with Hardcover."
LOGIN_FAILED = "invalid username or password"


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    event = parse_event(event)
    if "requestType" not in event:
        return http_result(400, "No requestType provided")

    if event["requestType"] == "register":
        # Registration by password is permanently off; accounts come from Hardcover sign-in.
        return http_result(403, REGISTER_DISABLED)

    db = _get_db()
    if "username" not in event:
        return http_result(403, "invalid input, missing username")
    if "password" not in event:
        return http_result(403, "invalid input, missing password")

    if event["requestType"] == "login":
        return _handle_login(db, event["username"], event["password"])
    else:
        return http_result(400, f"'{event['requestType']}' is an invalid requestType")


def _handle_login(db, username, password):
    user_data = db.get_user(username) if isinstance(username, str) and isinstance(password, str) else None
    # One message for unknown user, OAuth-only account (no password) and wrong password.
    if not user_data or not user_data.get("hashedPassword") or not user_data.get("salt"):
        return http_result(403, LOGIN_FAILED)
    if hash_and_salt(password, user_data["salt"]) != user_data["hashedPassword"]:
        return http_result(403, LOGIN_FAILED)
    if user_data.get("banned"):
        return http_result(403, "This account is not permitted to sign in.")
    session = mint_session(db, username)
    if session:
        return http_result(200, {"username": session["username"], "authtoken": session["authtoken"], "goodreads_id": session["goodreads_id"]})
    return http_result(400, "something went wrong, please try again later.")
