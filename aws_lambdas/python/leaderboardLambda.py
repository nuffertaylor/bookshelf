import boto3
from boto3.dynamodb.conditions import Key
from io import BytesIO

region = "us-east-1"
regionEndpoint = "https://dynamodb."+ region + ".amazonaws.com"
db_client = boto3.client("dynamodb", region)
dynamodb = boto3.resource('dynamodb', endpoint_url=regionEndpoint)
table = dynamodb.Table('bookshelf')

def handler(event, context):
  return

def fetchLeaderboard():
  return

def getNumberOfTotalSpines():
  res = table.scan(
    **{"Select" : "COUNT"}
  )
  return res["Count"]
  

def calcNumberOfUserSpines(username):

  results = []
  scan_kwargs = {
    "Select" : "COUNT",
    'FilterExpression': 'contains(#x, :val)',
    'ProjectionExpression': "title, book_id, dimensions, fileName, pubDate",
    'ExpressionAttributeNames': {
    '#x': "submitter"
    },
    'ExpressionAttributeValues': {
        ':val': username
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