from cockroachdb_dao import CockroachDAO
import os
db = CockroachDAO(os.getenv('DATABASE_URL'))

def httpResult(statusCode, body):
  return {"statusCode" : statusCode, "body" : body}

def lambda_handler(event, context):
  results = db.get_all_shelf_bgs()
  return(200, results)

# aws lambda update-function-code --function-name getShelfBgs --zip-file fileb://~/projects/bookshelf/aws_lambdas/python/lambda.zip
