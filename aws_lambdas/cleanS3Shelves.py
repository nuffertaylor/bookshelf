from aws_lambdas.dynamodb_dao import getAllShelfImages, delShelfImage
from s3_dao import delS3File

def lambda_handler(event, context):
  images = getAllShelfImages()
  for image in images:
    delS3File(image["filename"])
    delShelfImage(image["filename"])