from cockroachdb_dao import CockroachDAO
import os
db = CockroachDAO(os.getenv('DATABASE_URL'))

def httpResult(statusCode, body):
  return {"statusCode" : statusCode, "body" : body}

def lambda_handler(event, context):
  if("username" not in event.keys()): return httpResult(403, "Request failed, no username provided")
  if("filename" not in event.keys()): return httpResult(403, "Request failed, no filename provided")
  if("authtoken" not in event.keys()): return httpResult(403, "Request failed, no authtoken provided")
  bookshelf_name = event["bookshelf_name"] if event["bookshelf_name"] else ""
  if(len(bookshelf_name) > 64): bookshelf_name = bookshelf_name[:63]
  if(not db.validate_username_authtoken(event["username"], event["authtoken"])):
    return httpResult(403, "Request Failed, invalid authtoken")
  if(db.set_shelf_image_owner(event["filename"], event["username"], bookshelf_name)):
    return httpResult(200, "successfully set shelf image ownership")
  return httpResult(500, "something went wrong")