import os
import random
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.http import http_result

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def rand_str(num_char):
    return ''.join(random.choice("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(num_char))


def lambda_handler(event, context):
    db = _get_db()
    if "submitter" not in event:
        return http_result(403, "missing submitter")
    if "width_inches" not in event:
        return http_result(403, "missing width_inches")
    if "width_pixels" not in event:
        return http_result(403, "missing width_pixels")
    if "shelf_bottoms" not in event:
        return http_result(403, "missing shelf_bottoms")
    if "shelf_left" not in event:
        return http_result(403, "missing shelf_left")

    event["filename"] = rand_str(10) + ".jpg"
    title = event.get("title", "")

    if db.add_shelf_bg(event["submitter"], event["filename"], event["width_inches"], event["width_pixels"], event["shelf_bottoms"], event["shelf_left"], title):
        return http_result(200, "success")
    return http_result(500, "Something went wrong")
