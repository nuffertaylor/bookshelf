import os
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.http import http_result, parse_event

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    event = parse_event(event)
    db = _get_db()
    if "username" not in event:
        return http_result(403, "Request failed, no username provided")
    if "authtoken" not in event:
        return http_result(403, "Request failed, no authtoken provided")
    if "unfound" not in event:
        return http_result(403, "No unfound books provided to upload")
    if not isinstance(event["unfound"], list):
        return http_result(403, "unfound must be a list of books")
    if not db.validate_username_authtoken(event["username"], event["authtoken"]):
        return http_result(403, "Request failed, invalid authtoken")

    # Each book needs a Goodreads `book_id` and/or a `hardcover_book_id`; others are skipped.
    db.add_unfound_to_uploads(event["unfound"], event["username"])
    return http_result(200, "successfully added")
