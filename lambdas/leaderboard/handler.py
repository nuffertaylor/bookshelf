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
    return {"statusCode": 200, "body": db.get_leaderboard()}
