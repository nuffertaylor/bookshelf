import logging
import boto3
from botocore.exceptions import ClientError
import os
from PIL import Image


s3 = boto3.resource('s3')
s3_client = boto3.client('s3')


def upload_file(file_name, bucket="bookshelf-spines", object_name=None):
    if object_name is None:
        object_name = os.path.basename(file_name)

    print("attempting to upload " + object_name)
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        print(e)
        print("failed to upload " + object_name)
        return False
    print("sucessfully uploaded " + object_name)
    return True


def upload_fileobj(fileobj, object_name, bucket="bookshelf-spines"):
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
    bucket_obj = s3.Bucket(bucket)
    obj = bucket_obj.Object(file_name)
    response = obj.get()
    file_stream = response['Body']
    return Image.open(file_stream)


def delS3File(file_name, bucket="bookshelf-spines"):
    bucket_obj = s3.Bucket(bucket)
    obj = bucket_obj.Object(file_name)
    obj.delete()
