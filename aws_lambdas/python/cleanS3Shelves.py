import os
from s3_dao import delS3File
from cockroachdb_dao import CockroachDAO
db = CockroachDAO(os.getenv('DATABASE_URL'))


def lambda_handler(event, context):
  images = db.get_shelf_images_to_delete()
  for image in images:
    delS3File(image["filename"])
    db.delete_shelf_image(image["shelf_id"])
  return {"statusCode" : 200}