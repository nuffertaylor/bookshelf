import os
import time
from cockroachdb_dao import CockroachDAO
db = CockroachDAO(os.getenv('DATABASE_URL'))

def br(code, body):
  return {"statusCode" : code, "body" : body}

def lambda_handler(event, context):
  if("username" not in event.keys()): return br(403, "missing username")
  if("authtoken" not in event.keys()): return br(403, "missing authtoken")
  if("goodreads_id" not in event.keys()): return br(403, "missing goodreads_id to set")
  user = db.get_user(event["username"])
  if(not user): return br(403, "couldn't find user " + event["username"])
  if(user["authtoken"] != event["authtoken"] or user["expiry"] < int(time.time())):
    return br(403, "invalid authtoken")
  if(db.update_user_col(event["username"], "goodreads_id", event["goodreads_id"])):
    user["goodreads_id"] = event["goodreads_id"]
    return br(200, user)
  return br(400, "something went wrong")