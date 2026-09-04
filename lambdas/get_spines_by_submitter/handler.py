import os
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.http import http_result

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    db = _get_db()
    if "username" not in event:
        return http_result(403, "Request failed, no username provided")
    books = db.get_books_by_submitter(event["username"])
    if not books:
        return http_result(200, [])
    return http_result(200, books)
