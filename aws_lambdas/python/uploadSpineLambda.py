from base64 import b64decode
from cockroachdb_dao import CockroachDAO
from io import BytesIO
import os
from s3_dao import upload_fileobj
import time

db = CockroachDAO(os.getenv('DATABASE_URL'))

def create_filename(title, book_id, extension):
  t = ''.join(ch for ch in title if ch.isalnum())
  return t + "-" + book_id + "." + extension

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

def lambda_handler(event, context):
  if(not verify_required_values(event)):
    return build_return(403, error_message)
    
  if(not validate_username_authtoken(event["username"], event["authtoken"])):
    return build_return(403, error_message)

  extension = get_ext_from_b64(event["image"])
  b64str = pad_b64_str(event["image"])
  decoded = b64decode(b64str)
  temp_file = BytesIO(decoded)
  file_name = create_filename(event["title"], event["book_id"], extension)
  result = False
  
  if(upload_fileobj(temp_file, object_name=file_name)):
    event["fileName"] = file_name
    result = db.add_book(event)

  if(result):
    #result object is {upload_id : id}
    return build_return(200, result)
  return build_return(500, "failed to upload spine for " + event["title"])
