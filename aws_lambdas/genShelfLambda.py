from bookshelf import Bookshelf
from dynamodb_dao import putShelfImage
import os
import random
from s3_dao import upload_file, openS3Image
import string

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
  bookshelf.fillShelf(sortedBooks)
  os.chdir("/tmp")
  fileName = rand_str(10) + ".jpg"
  bookshelf.saveShelf(fileName)
  if(upload_file(fileName)):
    putShelfImage(fileName)
    image_url = "https://bookshelf-spines.s3.amazonaws.com/" + fileName
    return build_return(200, image_url)