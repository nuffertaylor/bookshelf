from cockroachdb_dao import CockroachDAO
from colorthief import ColorThief
import os
from PIL import Image # type: ignore
import urllib.request
db = CockroachDAO(os.getenv('DATABASE_URL'))

error_message = "Something went wrong." 

def build_return(code, msg):
  return {"statusCode" : code, "body" : msg}

def rgb_to_hex(rgb : tuple):
  return "#%02x%02x%02x" % rgb

def calcDomRGB(source):
  cf = ColorThief(source)
  dominant = cf.get_color(quality=1)
  return rgb_to_hex(dominant)

def verify_required_values(event):
  required_items = [
    # "title",
    # "book_id",
    "upload_id"
  ]

  for item in required_items:
    if((item not in event.keys()) or (event[item] == None) or (event[item] == "")):
      global error_message
      error_message = "Did not have the required item '" + item + "'."
      return False
  return True

def lambda_handler(event, context):
  if(not verify_required_values(event)):
    return build_return(403, error_message)
  book = db.get_book_by("upload_id", event["upload_id"])
  title = book["title"]
  os.chdir("/tmp")
  urllib.request.urlretrieve(
    "https://bookshelf-spines.s3.amazonaws.com/" + book["fileName"],
    "temp.png")
  book["domColor"] = calcDomRGB("temp.png")
  if(db.update_book_col(book["upload_id"], "domColor", book["domColor"])):
    return build_return(200, "updated color of " + title + " to " + book["domColor"])
  return build_return(400, "something went wrong setting the updated domColor")

#note: no longer used