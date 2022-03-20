import boto3
from boto3.dynamodb.conditions import Key

region = "us-east-1"
regionEndpoint = "https://dynamodb."+ region + ".amazonaws.com"
db_client = boto3.client("dynamodb", region)
dynamodb = boto3.resource('dynamodb', endpoint_url=regionEndpoint)
table = dynamodb.Table('bookshelf')

def handler(event, context):
  if(event["title"]):
    return {"statusCode" : 200, "body" : searchByTitle(event["title"])}
  elif(event["bookid"]):
    return {"statusCode" : 200, "body" : searchByTitle(event["bookid"])}
  else:
    return {"statusCode" : 400, "body" : event} 

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
    'ProjectionExpression': "title, book_id, dimensions, fileName, pubDate",
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