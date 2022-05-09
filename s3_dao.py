import logging
import boto3
from botocore.exceptions import ClientError
import os
from PIL import Image


s3 = boto3.resource('s3')
s3_client = boto3.client('s3')

def upload_file(file_name, bucket="bookshelf-spines", object_name=None):
  """Upload a file to an S3 bucket

  :param file_name: File to upload
  :param bucket: Bucket to upload to
  :param object_name: S3 object name. If not specified then file_name is used
  :return: True if file was uploaded, else False
  """

  # If S3 object_name was not specified, use file_name
  if object_name is None:
    object_name = os.path.basename(file_name)

  # Upload the file
  print("attempting to upload " + object_name)
  try:
    response = s3_client.upload_file(file_name, bucket, object_name)
  except ClientError as e:
    print(e)
    print("failed to upload " + object_name)
    return False
  print("sucessfully uploaded " + object_name)
  return True

def upload_fileobj(fileobj, object_name, bucket="bookshelf-spines", ):
  """Upload a file to an S3 bucket

  :param file_obj: File to upload
  :param object_name: S3 object name. since we're uploading bytes, this must be specified
  :param bucket: Bucket to upload to
  """

  # Upload the file
  print("attempting to upload " + object_name)
  try:
    response = s3_client.upload_fileobj(fileobj, bucket, object_name)
  except ClientError as e:
    print(e)
    print("failed to upload " + object_name)
    return False
  print("sucessfully uploaded " + object_name)
  return True


def openS3Image(file_name, bucket="bookshelf-spines"):
  bucket = s3.Bucket(bucket)
  obj = bucket.Object(file_name)
  response = obj.get()
  file_stream = response['Body']
  return Image.open(file_stream)


def delS3File(file_name, bucket="bookshelf-spines"):
  bucket = s3.Bucket(bucket)
  obj = bucket.Object(file_name)
  obj.delete()