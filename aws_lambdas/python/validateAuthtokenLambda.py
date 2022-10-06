from distutils.command.build import build
import os
from cockroachdb_dao import CockroachDAO
db = CockroachDAO(os.getenv('DATABASE_URL'))

def build_return(code, msg):
  return {"statusCode" : code, "valid_authtoken" : msg}

def lambda_handler(event, context):
  if("username" not in event or "authtoken" not in event):
    return build_return(403, False)
  valid = db.validate_username_authtoken(event["username"], event["authtoken"])
  return build_return(200, valid)