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
    if "bg_id" in event and event["bg_id"]:
        results = db.get_shelf_bg_by_bg_id(event["bg_id"])
        if not results:
            results = {}
    elif "filename" in event and event["filename"]:
        results = db.get_shelf_bg_by_filename(event["filename"])
        if not results:
            results = {}
    else:
        results = db.get_all_shelf_bgs()
        if not results:
            results = []
    return http_result(200, results)
