from base64 import b64decode
from colorthief import ColorThief
from distutils.log import error
from dynamodb_dao import putBook, getUser
from io import BytesIO
import os
from s3_dao import upload_fileobj
import time

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
  user = getUser(username)
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

def rgb_to_hex(rgb : tuple):
  return "#%02x%02x%02x" % rgb

def calcDomRGB(source):
  cf = ColorThief(source)
  dominant = cf.get_color(quality=1)
  return rgb_to_hex(dominant)
  
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
  
  # b64str = pad_b64_str(event["image"])
  # tempFile = saveB64TempFile(b64str)
  # domColor = calcDomRGB(tempFile)
  #instead of doing long computation here, send sqs and append that data to the db when the calc is finished

  if(upload_fileobj(temp_file, object_name=file_name)):
    result= putBook(title=event["title"], 
            book_id=event["book_id"], 
            pubDate=event["pubDate"], 
            author=event["authorName"],
            fileName=file_name,
            dimensions=event["dimensions"],
            genre=event["genre"],
            submitter=event["username"],
            #domColor=domColor
            )

  if(result):
    #send calcdomcolor sqs
    
    return build_return(200, "successfully inserted " + event["title"])
  else:
    return build_return(500, "failed to upload spine for " + event["title"])
