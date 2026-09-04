import os
from bookshelf.dao.cockroachdb_dao import CockroachDAO

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    db = _get_db()
    if "username" not in event or "authtoken" not in event:
        return {"statusCode": 403, "valid_authtoken": False}
    valid = db.validate_username_authtoken(event["username"], event["authtoken"])
    return {"statusCode": 200, "valid_authtoken": valid}
