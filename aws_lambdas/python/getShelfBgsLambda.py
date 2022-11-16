from cockroachdb_dao import CockroachDAO
import os
db = CockroachDAO(os.getenv('DATABASE_URL'))

def httpResult(statusCode, body):
  return {"statusCode" : statusCode, "body" : body}

def lambda_handler(event, context):
  results = None
  if("bg_id" in event.keys() and event["bg_id"]):
    results = db.get_shelf_bg_by_bg_id(event["bg_id"])
  elif("filename" in event.keys() and event["filename"]):
    results = db.get_shelf_bg_by_filename(event["filename"])
  else:
    results = db.get_all_shelf_bgs()
  if(results):
    return(200, results)
  return(200, [])

# aws lambda update-function-code --function-name getShelfBgs --zip-file fileb://~/projects/bookshelf/aws_lambdas/python/lambda.zip
