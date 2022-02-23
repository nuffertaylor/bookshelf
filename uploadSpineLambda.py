from base64 import b64decode
from distutils.log import error
from dynamodb_dao import putBook
from s3_dao import upload_fileobj

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
    "dimensions"
  ]

  for item in required_items:
    if((item not in event.keys()) or (event[item] == None) or (event[item] == "")):
      error_message = "Did not have the required item '" + item + "'."
      return False
  return True

def pad_b64_str(b64str):
  numCharToAdd = len(b64str) % 4
  if(numCharToAdd > 0):
    a = b64str.split(',')
    b = a[1]
    a = a[0]
    for i in range(numCharToAdd):
      b = '0' + b
    return a + b
  else:
    return b64str
  
def lambda_handler(event, context):
  if(not verify_required_values(event)):
    return build_return(400, error_message)

  extension = get_ext_from_b64(event["image"])
  b64str = pad_b64_str(event["image"])
  decoded = b64decode(b64str)
  file_name = create_filename(event["title"], event["book_id"], extension)
  result = False

  if(upload_fileobj(decoded, object_name=file_name)):
    result= putBook(title=event["title"], 
            book_id=event["book_id"], 
            pubDate=event["pubDate"], 
            author=event["authorName"],
            fileName=file_name,
            dimensions=event["dimensions"],
            genre=event["genre"]
            )

  if(result):
    return build_return(200, "successfully inserted " + event["title"])
  else:
    return build_return(500, "failed to upload spine for " + event["title"])
