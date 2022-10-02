from cockroachdb_dao import CockroachDAO
import os
db = CockroachDAO(os.getenv('DATABASE_URL'))

def httpResult(statusCode, body):
  return {"statusCode" : statusCode, "body" : body}

def lambda_handler(event, context):
  if("username" not in event.keys()): return httpResult(403, "Request failed, no username provided")
  res = db.get_shelf_images_by_owner(event["username"])
  if(res): return httpResult(200, res)
  if(len(res) == 0): return httpResult(200, [])
  return httpResult(500, "something went wrong")