from bookshelf import Bookshelf
from cockroachdb_dao import CockroachDAO
import os
import random
from s3_dao import upload_file, openS3Image
import string
db = CockroachDAO(os.getenv('DATABASE_URL'))

def build_return(code, msg):
  return {"statusCode" : code, "body" : msg}

def rand_str(n = 5):
  letters = string.ascii_lowercase
  return ''.join(random.choice(letters) for i in range(n))
  
class S3ImageOpener:
  def open(filename):
    return openS3Image(filename)

def lambda_handler(event, context):
  sortedBooks = event["bookList"]
  bookshelf = Bookshelf(S3ImageOpener, "bookshelf1.jpg", 35.5, 1688, [676, 1328, 2008, 2708, 3542], 75)
  os.chdir("/tmp")
  bookshelf.fillShelf(sortedBooks)
  filename = rand_str(10) + ".jpg"
  bookshelf.saveShelf(filename)
  if("gr_shelf_name" not in event.keys()): event["gr_shelf_name"] = ""
  if("gr_user_id" not in event.keys()): event["gr_user_id"] = ""
  if(upload_file(filename)):
    db.add_shelf_image(filename, event["gr_shelf_name"], event["gr_user_id"])
    shelf_image = db.get_shelf_image_by_filename(filename)
    return build_return(200, shelf_image)
  return build_return(400, "bookshelf creation failed")