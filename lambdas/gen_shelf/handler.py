import os
import random
import string
from bookshelf.bookshelf import Bookshelf
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.dao.s3_dao import upload_file, openS3Image
from bookshelf.http import http_result

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def rand_str(n=5):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for _ in range(n))


class S3ImageOpener:
    def open(filename):
        return openS3Image(filename)


def lambda_handler(event, context):
    db = _get_db()
    sorted_books = event["bookList"]
    bookshelf = Bookshelf(S3ImageOpener, "bookshelf1.jpg", 35.5, 1688, [676, 1328, 2008, 2708, 3542], 75)
    os.chdir("/tmp")
    bookshelf.fillShelf(sorted_books)
    filename = rand_str(10) + ".jpg"
    bookshelf.saveShelf(filename)
    if "gr_shelf_name" not in event:
        event["gr_shelf_name"] = ""
    if "gr_user_id" not in event:
        event["gr_user_id"] = ""
    if upload_file(filename):
        db.add_shelf_image(filename, event["gr_shelf_name"], event["gr_user_id"])
        shelf_image = db.get_shelf_image_by_filename(filename)
        return http_result(200, shelf_image)
    return http_result(400, "bookshelf creation failed")
