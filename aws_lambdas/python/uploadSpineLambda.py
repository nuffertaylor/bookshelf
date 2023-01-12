from base64 import b64decode
from cockroachdb_dao import CockroachDAO
from io import BytesIO
import os
import random
import re
from s3_dao import upload_fileobj, delS3File
import time

db = CockroachDAO(os.getenv('DATABASE_URL'))
MAX_UPLOAD_SIZE_BYTES = 6291456

def rand_str(num_char):
  return ''.join(random.choice("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") for i in range(num_char))

def create_filename(title, book_id, extension):
  t = ''.join(ch for ch in title if ch.isalnum())
  t = re.sub(r'[^\x00-\x7f]',r'', t)
  return t + "-" + str(book_id) +  "-" + rand_str(10) + "." + extension

def get_ext_from_b64(b64str):
  a = b64str.split(';')[0]
  b = a.split('/')[1]
  return b

def build_return(code, msg):
  return {"statusCode" : code, "body" : msg}

error_message = "Something went wrong." 

def verify_required_values(event):
  required_items = [
    "image",
    "title",
    "book_id",
    "dimensions",
    "username",
    "authtoken"
  ]

  for item in required_items:
    if((item not in event.keys()) or (event[item] == None) or (event[item] == "")):
      global error_message
      error_message = "Did not have the required item '" + item + "'."
      return False
  return True

def validate_username_authtoken(username, authtoken):
  global error_message
  user = db.get_user(username)
  if(not user): 
    error_message = "invalid username"
    return False
  if(authtoken != user["authtoken"]):
    error_message = "invalid authtoken"
    return False
  if(int(time.time()) > int(user["expiry"])):
    error_message = "expired authtoken"
    return False
  return True

def pad_b64_str(b64str):
  a = b64str.split(',')
  return a[1]

def saveB64TempFile(b64str):
  os.chdir('/tmp')
  b64Type = get_ext_from_b64(b64str)
  fileName = "temp_image." + b64Type
  image = open(fileName, "wb")
  image.write(b64decode(b64str))
  image.close()
  return fileName

def create_and_upload_img(event):
  extension = get_ext_from_b64(event["image"])
  b64str = pad_b64_str(event["image"])
  decoded = b64decode(b64str)
  temp_file = BytesIO(decoded)
  file_name = create_filename(event["title"], event["book_id"], extension)
  
  if(upload_fileobj(temp_file, object_name=file_name)):
    return file_name
  return False

def lambda_handler(event, context):
  if(not verify_required_values(event)):
    return build_return(403, error_message)
    
  if(not validate_username_authtoken(event["username"], event["authtoken"])):
    return build_return(403, error_message)

  keep_upload = ("keep_upload" in event and event["keep_upload"])

  if(not keep_upload):
    #b64 encodes 3 bytes of data in 4 char, so byte size will be 3/4
    if(len(event["image"]) * 0.75 > MAX_UPLOAD_SIZE_BYTES):
      return build_return(403, "File user attempted to upload is too large.")

    file_name = create_and_upload_img(event)
    if(not file_name):
      return build_return(500, "failed to upload spine for " + event["title"])

  existing_record = db.has_username_uploaded_book(event["username"], event["book_id"])
  if(existing_record):
    if("replace_img" not in event):
      result = {
        "upload_id" : existing_record["upload_id"],
        "already_uploaded" : True,
        "fileName" : existing_record["fileName"]
      }
      return build_return(200, result)
    #if this is a replace request:
    if("replace_img" in event and event["replace_img"] and "upload_id" in event):
      book = db.get_book_by("upload_id", event["upload_id"])
      #if keep_upload, use previous file and domcolor
      if(keep_upload):
        file_name = book["fileName"]
        event["domColor"] = book["domColor"]
      #else it's a new image upload
      else:
        delS3File(book["fileName"])
      #delete old row, make a new one with changed data
      db.delete_book(event["upload_id"])

  event["fileName"] = file_name
  result = db.add_book(event)
  result["already_uploaded"] = False
  #result object is {upload_id : string, already_uploaded: boolean}
  return build_return(200, result)

# zip -r lambda.zip .
# aws lambda update-function-code --function-name uploadSpine --zip-file fileb://~/projects/bookshelf/aws_lambdas/python/lambda.zip