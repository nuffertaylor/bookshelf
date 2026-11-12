import os

from bookshelf import hardcover_client
from bookshelf.bookshelf import which_books_found
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.hardcover_http import error_response
from bookshelf.hardcover_library import ShelfNotFound, get_shelf_books
from bookshelf.http import http_result, parse_event

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    """POST /hardcover/shelf {"username", "authtoken", "shelf": "status:3" | "list:456"}
    -> {"found": [...], "unfound": [...]} (same shape as getgrbookshelf). The library is fetched per
    request and never stored."""
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
    shelf = event.get("shelf")
    if not isinstance(shelf, str) or not shelf:
        return http_result(400, {"error": "shelf is required"})
    db = _get_db()
    if not db.validate_username_authtoken(username, authtoken):
        return http_result(403, {"error": "invalid or expired session"})

    try:
        books = get_shelf_books(db, username, shelf)
    except ShelfNotFound:
        return http_result(404, {"error": "shelf not found"})
    except (hardcover_client.HardcoverReauthRequired, hardcover_client.HardcoverError) as e:
        return error_response(e)

    found, unfound = which_books_found(db, books)
    return http_result(200, {"found": found, "unfound": unfound})
