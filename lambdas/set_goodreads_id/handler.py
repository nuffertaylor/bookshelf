import os
import time
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
        return http_result(403, "missing username")
    if "authtoken" not in event:
        return http_result(403, "missing authtoken")
    if "goodreads_id" not in event:
        return http_result(403, "missing goodreads_id to set")
    user = db.get_user(event["username"])
    if not user:
        return http_result(403, "couldn't find user " + event["username"])
    if user["authtoken"] != event["authtoken"] or user["expiry"] < int(time.time()):
        return http_result(403, "invalid authtoken")
    if db.update_user_col(event["username"], "goodreads_id", event["goodreads_id"]):
        user["goodreads_id"] = event["goodreads_id"]
        return http_result(200, user)
    return http_result(400, "something went wrong")
