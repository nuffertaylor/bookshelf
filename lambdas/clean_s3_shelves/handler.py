import os
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.dao.s3_dao import delS3File

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    db = _get_db()
    images = db.get_shelf_images_to_delete()
    for image in images:
        delS3File(image["filename"])
        db.delete_shelf_image(image["shelf_id"])
    return {"statusCode": 200}
