from cockroachdb_dao import CockroachDAO
import os
db = CockroachDAO(os.getenv('DATABASE_URL'))

def httpResult(statusCode, body):
  return {"statusCode" : statusCode, "body" : body}

def lambda_handler(event, context):
  if("username" not in event.keys()): return httpResult(403, "Request failed, no username provided")
  if("filename" not in event.keys()): return httpResult(403, "Request failed, no filename provided")
  if("authtoken" not in event.keys()): return httpResult(403, "Request failed, no authtoken provided")
  if("bookshelf_name" not in event.keys()): event["bookshelf_name"] = ""
  if(len(event["bookshelf_name"]) > 64): event["bookshelf_name"] = event["bookshelf_name"][:63]

  shelf_image = db.get_shelf_image_by_filename(event["filename"])
  if(shelf_image["owner"] and shelf_image["owner"] != event["username"]):
    return httpResult(403, "Request Failed, shelf already claimed by different user.")
  if(not db.validate_username_authtoken(event["username"], event["authtoken"])):
    return httpResult(403, "Request Failed, invalid authtoken")
  if(db.set_shelf_image_owner(event["filename"], event["username"], event["bookshelf_name"])):
    shelf_image["owner"] = event["username"]
    shelf_image["bookshelf_name"] = event["bookshelf_name"]
    return httpResult(200, shelf_image)
  return httpResult(500, "something went wrong")