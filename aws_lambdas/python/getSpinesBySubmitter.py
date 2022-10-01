from cockroachdb_dao import CockroachDAO
import os
db = CockroachDAO(os.getenv('DATABASE_URL'))

def httpResult(statusCode, body):
  return {"statusCode" : statusCode, "body" : body}

def lambda_handler(event, context):
  if("username" not in event.keys()): return httpResult(403, "Request failed, no username provided")

  books = db.get_books_by_submitter(event["username"])
  if(not books): return httpResult(200, [])
  return httpResult(200, books)

# Compress-Archive . lambda.zip