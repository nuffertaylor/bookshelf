from base64 import b64decode
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.dao.s3_dao import upload_fileobj, delS3File
from bookshelf.http import http_result
from io import BytesIO
import os
import random
import re
import time

_db = None
MAX_UPLOAD_SIZE_BYTES = 6291456


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def rand_str(num_char):
    return ''.join(random.choice("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(num_char))


def create_filename(title, book_id, extension):
    t = ''.join(ch for ch in title if ch.isalnum())
    t = re.sub(r'[^\x00-\x7f]', r'', t)
    return t + "-" + str(book_id) + "-" + rand_str(10) + "." + extension


def get_ext_from_b64(b64str):
    a = b64str.split(';')[0]
    b = a.split('/')[1]
    return b


def pad_b64_str(b64str):
    a = b64str.split(',')
    return a[1]


_error_message = "Something went wrong."


def verify_required_values(event):
    global _error_message
    required_items = ["image", "title", "book_id", "dimensions", "username", "authtoken"]
    for item in required_items:
        if (item not in event.keys()) or (event[item] is None) or (event[item] == ""):
            _error_message = f"Did not have the required item '{item}'."
            return False
    return True


def validate_username_authtoken(db, username, authtoken):
    global _error_message
    user = db.get_user(username)
    if not user:
        _error_message = "invalid username"
        return False
    if authtoken != user["authtoken"]:
        _error_message = "invalid authtoken"
        return False
    if int(time.time()) > int(user["expiry"]):
        _error_message = "expired authtoken"
        return False
    return True


def create_and_upload_img(event):
    extension = get_ext_from_b64(event["image"])
    b64str = pad_b64_str(event["image"])
    decoded = b64decode(b64str)
    temp_file = BytesIO(decoded)
    file_name = create_filename(event["title"], event["book_id"], extension)
    if upload_fileobj(temp_file, object_name=file_name):
        return file_name
    return False


def lambda_handler(event, context):
    db = _get_db()
    if not verify_required_values(event):
        return http_result(403, _error_message)

    if not validate_username_authtoken(db, event["username"], event["authtoken"]):
        return http_result(403, _error_message)

    keep_upload = ("keep_upload" in event and event["keep_upload"])

    if not keep_upload:
        if len(event["image"]) * 0.75 > MAX_UPLOAD_SIZE_BYTES:
            return http_result(403, "File user attempted to upload is too large.")
        file_name = create_and_upload_img(event)
        if not file_name:
            return http_result(500, "failed to upload spine for " + event["title"])

    existing_record = db.has_username_uploaded_book(event["username"], event["book_id"])
    if existing_record:
        if "replace_img" not in event:
            result = {
                "upload_id": existing_record["upload_id"],
                "already_uploaded": True,
                "fileName": existing_record["fileName"],
            }
            return http_result(200, result)
        if "replace_img" in event and event["replace_img"] and "upload_id" in event:
            book = db.get_book_by("upload_id", event["upload_id"])
            if keep_upload:
                file_name = book["fileName"]
                event["domColor"] = book["domColor"]
            else:
                delS3File(book["fileName"])
            db.delete_book(event["upload_id"])

    event["fileName"] = file_name
    result = db.add_book(event)
    result["already_uploaded"] = False
    return http_result(200, result)
