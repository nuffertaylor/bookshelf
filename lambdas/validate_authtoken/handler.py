import os
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.http import http_result_raw, parse_event

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    event = parse_event(event)
    db = _get_db()
    if "username" not in event or "authtoken" not in event:
        return http_result_raw(403, {"statusCode": 403, "valid_authtoken": False})
    valid = db.validate_username_authtoken(event["username"], event["authtoken"])
    return http_result_raw(200, {"statusCode": 200, "valid_authtoken": valid})
