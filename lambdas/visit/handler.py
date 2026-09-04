import os
import time
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.http import http_result

_db = None
WAITING_PERIOD = 60 * 10


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    db = _get_db()
    if "ip" not in event:
        return http_result(403, "missing ip")
    previous_visitor = db.get_visitor_by_ip(event["ip"])
    if not previous_visitor:
        if "os" not in event:
            event["os"] = "unknown"
        if "browser" not in event:
            event["browser"] = "unknown"
        if db.add_visitor(event):
            return http_result(200, "success")
        return http_result(500, "Error logging new visitor")
    if int(previous_visitor["timestamp"]) > int(time.time()) - WAITING_PERIOD:
        return http_result(200, "unlogged, repeat visit")
    if db.update_visit_count(previous_visitor["visitor_id"], previous_visitor["num_visits"]):
        return http_result(200, "success")
    return http_result(500, "Error logging visit")
