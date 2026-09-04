from base64 import b64decode
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.dao.s3_dao import upload_fileobj
from bookshelf.http import http_result
from io import BytesIO
import os
import random
import re

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def rand_str(num_char):
    return ''.join(random.choice("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(num_char))


def pad_b64_str(b64str):
    a = b64str.split(',')
    return a[1]


def get_ext_from_b64(b64str):
    a = b64str.split(';')[0]
    b = a.split('/')[1]
    return b


def create_filename(title, extension):
    t = ''.join(ch for ch in title if ch.isalnum())
    t = re.sub(r'[^\x00-\x7f]', r'', t)
    return t + "-" + rand_str(10) + "." + extension


def set_shelf_image_owner(db, event, shelf_image):
    if db.set_shelf_image_owner(event["filename"], event["username"], event["bookshelf_name"]):
        shelf_image["owner"] = event["username"]
        shelf_image["bookshelf_name"] = event["bookshelf_name"]
        return http_result(200, shelf_image)
    return http_result(500, "something went wrong")


def handle_existing_file(db, event):
    shelf_image = db.get_shelf_image_by_filename(event["filename"])
    if shelf_image["owner"] and shelf_image["owner"] != event["username"]:
        return http_result(403, "Request Failed, shelf already claimed by different user.")
    if "delete_owner" in event and event["delete_owner"]:
        event["username"] = ""
    return set_shelf_image_owner(db, event, shelf_image)


def create_and_upload_shelf(event):
    extension = get_ext_from_b64(event["b64_shelf_image"])
    b64str = pad_b64_str(event["b64_shelf_image"])
    decoded = b64decode(b64str)
    temp_file = BytesIO(decoded)
    file_name = create_filename(event["bookshelf_name"], extension)
    if upload_fileobj(temp_file, object_name=file_name):
        return file_name
    return False


def handle_upload_new_shelf(db, event):
    event["filename"] = create_and_upload_shelf(event)
    if db.add_shelf_image_and_owner(event["filename"], event["username"], event["bookshelf_name"]):
        return http_result(200, event)
    return http_result(500, "something went wrong uploading your bookshelf.")


def lambda_handler(event, context):
    db = _get_db()
    if "username" not in event:
        return http_result(403, "Request failed, no username provided")
    if "authtoken" not in event:
        return http_result(403, "Request failed, no authtoken provided")
    if "bookshelf_name" not in event:
        event["bookshelf_name"] = ""
    if len(event["bookshelf_name"]) > 64:
        event["bookshelf_name"] = event["bookshelf_name"][:63]
    if not db.validate_username_authtoken(event["username"], event["authtoken"]):
        return http_result(403, "Request Failed, invalid authtoken")

    if "b64_shelf_image" in event and event["b64_shelf_image"] != "":
        return handle_upload_new_shelf(db, event)
    elif "filename" in event:
        return handle_existing_file(db, event)
