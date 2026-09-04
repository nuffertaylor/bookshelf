import os
import urllib.request
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.http import http_result
from colorthief import ColorThief

_db = None
_error_message = "Something went wrong."


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def rgb_to_hex(rgb: tuple):
    return "#%02x%02x%02x" % rgb


def calcDomRGB(source):
    cf = ColorThief(source)
    dominant = cf.get_color(quality=1)
    return rgb_to_hex(dominant)


def verify_required_values(event):
    global _error_message
    if "upload_id" not in event or event["upload_id"] is None or event["upload_id"] == "":
        _error_message = "Did not have the required item 'upload_id'."
        return False
    return True


def lambda_handler(event, context):
    db = _get_db()
    if not verify_required_values(event):
        return http_result(403, _error_message)
    book = db.get_book_by("upload_id", event["upload_id"])
    title = book["title"]
    os.chdir("/tmp")
    urllib.request.urlretrieve(
        "https://bookshelf-spines.s3.amazonaws.com/" + book["fileName"],
        "temp.png",
    )
    book["domColor"] = calcDomRGB("temp.png")
    if db.update_book_col(book["upload_id"], "domColor", book["domColor"]):
        return http_result(200, "updated color of " + title + " to " + book["domColor"])
    return http_result(400, "something went wrong setting the updated domColor")
