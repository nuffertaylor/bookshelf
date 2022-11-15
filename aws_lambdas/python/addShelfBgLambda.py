from cockroachdb_dao import CockroachDAO
import os
import random
db = CockroachDAO(os.getenv('DATABASE_URL'))

def httpResult(statusCode, body):
  return {"statusCode" : statusCode, "body" : body}
  
def rand_str(num_char):
  return ''.join(random.choice("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") for i in range(num_char))
 
def lambda_handler(event, context):
  if("submitter" not in event.keys()): return(403, "missing submitter")
  if("width_inches" not in event.keys()): return(403, "missing width_inches")
  if("width_pixels" not in event.keys()): return(403, "missing width_pixels")
  if("shelf_bottoms" not in event.keys()): return(403, "missing shelf_bottoms")
  if("shelf_left" not in event.keys()): return(403, "missing shelf_left")
  #TODO: add validation for b64 image in upload
    
  #we generate filename
  event["filename"] = rand_str(10) + ".jpg"

  if(db.add_shelf_bg(event["submitter"], event["filename"], event["width_inches"], event["width_pixels"], event["shelf_bottoms"], event["shelf_left"])):
    return httpResult(200, "success")
  return httpResult(500, "Something went wrong")

# aws lambda update-function-code --function-name addShelfBg --zip-file fileb://~/projects/bookshelf/aws_lambdas/python/lambda.zip