import boto3
from boto3.dynamodb.conditions import Key
from dynamodb_dao import getBook
from s3_dao import openS3Image
from io import BytesIO
import base64

region = "us-east-1"
regionEndpoint = "https://dynamodb."+ region + ".amazonaws.com"
db_client = boto3.client("dynamodb", region)
dynamodb = boto3.resource('dynamodb', endpoint_url=regionEndpoint)
table = dynamodb.Table('bookshelf')

def handler(event, context):
  book = None
  if("title" not in event.keys()):
    return {"statusCode": 400, "body": "title required in order to get spine"}
  book = (getBook(event))
  if(book):
    # bytes = openS3Image(book["fileName"]).read()
    # img = base64.b64encode(bytes).decode()
    # book["image"] = img
    book["url"] = "https://bookshelf-spines.s3.amazonaws.com/" + book["fileName"]
    return {"statusCode" : 200, "body" : book}
  
  else:
    return {"statusCode" : 400, "body" : "no matching books found"} 

def get_spine(book_id):
  pass
    
def searchByTitle(title):
  return sendQuery("title", title)
        
def searchByBookId(bookid):
  return sendQuery("book_id", bookid)

def sendQuery(colName, val):
  results = []
  scan_kwargs = {
    'FilterExpression': 'contains(#x, :val)',
    'ProjectionExpression': "title, book_id, author, dimensions, domColor, fileName, genre, pubDate, submitter",
    'ExpressionAttributeNames': {
    '#x': colName
    },
    'ExpressionAttributeValues': {
        ':val': val
    },
  }
  done = False
  start_key = None
  while not done:
    if start_key:
      scan_kwargs['ExclusiveStartKey'] = start_key
    response = table.scan(**scan_kwargs)
    results = results + (response.get('Items', []))
    start_key = response.get('LastEvaluatedKey', None)
    done = start_key is None
      
  return results