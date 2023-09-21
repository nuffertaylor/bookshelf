from cockroachdb_dao import CockroachDAO
import os
db = CockroachDAO(os.getenv('DATABASE_URL'))

def httpResult(statusCode, body):
  return {"statusCode" : statusCode, "body" : body}

def lambda_handler(event, context):
  if("username" not in event.keys()): return httpResult(403, "Request failed, no username provided")
  if("authtoken" not in event.keys()): return httpResult(403, "Request failed, no username provided")
  if("unfound" not in event.keys()): return httpResult(403, "No unfound books provided to upload")
  if(not db.validate_username_authtoken(event["username"], event["authtoken"])): return httpResult(403, "Request failed, invalid authtoken")


  db.add_unfound_to_uploads(event["unfound"], event["username"])

  return httpResult(200, "successfully added")