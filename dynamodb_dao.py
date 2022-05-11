import boto3
from boto3.dynamodb.types import TypeDeserializer
from boto3.dynamodb.conditions import Key
import time

region = "us-east-1"
regionEndpoint = "https://dynamodb."+ region + ".amazonaws.com"
dynamodb = boto3.resource('dynamodb', endpoint_url=regionEndpoint)
db_client = boto3.client("dynamodb", region)
table = dynamodb.Table('bookshelf')
usertable = dynamodb.Table('bookshelf-users')
shelftable = dynamodb.Table('shelf-images')
deserializer = TypeDeserializer()

def split_list(a_list):
  #stackoverflow.com/questions/752308
  half = len(a_list)//2
  return a_list[:half], a_list[half:]

def get_update_params(body):
  """Given a dictionary we generate an update expression and a dict of values
  to update a dynamodb table.

  Params:
    body (dict): Parameters to use for formatting.

  Returns:
    update expression, dict of values.
  """
  update_expression = ["set "]
  update_values = dict()

  for key, val in body.items():
    update_expression.append(f" {key} = :{key},")
    update_values[f":{key}"] = val

  return "".join(update_expression)[:-1], update_values

"""BOOKSHELF TABLE"""

def putBook(title, book_id, pubDate = "", author = "", isbn = "", isbn13 = "", fileName = "", dimensions = "", domColor = "", genre = "", submitter = ""):

  data = {
      "title" : title,
      "book_id" : book_id,
      "pubDate" : pubDate,
      "author" : author,
      "isbn" : isbn,
      "isbn13" : isbn13,
      "fileName" : fileName,
      "dimensions" : dimensions,
      "domColor" : domColor,
      "genre" : genre,
      "submitter" : submitter
    }
  print("attempting to put data for " + title + " : " + book_id)
  try:
    res = table.put_item(Item=data)
    print("successfully put data for " + title + " : " + book_id)
    return res
  except Exception as e:
    print(e)
    print("failed to put data for " + title + " : " + book_id)
    return False

def getBookBatch(books):
  keyList = []
  if(len(books) > 99): #max batch request size is 100. so we'll recursively split the list if it's too big
    a, b = split_list(books)
    return getBookBatch(a) + getBookBatch(b)
  for book in books:
    key = {"title" : {"S" : book["title"]}, "book_id" : {"S" : book["book_id"]}}
    keyList.append(key)
  res = db_client.batch_get_item( RequestItems = { "bookshelf": { "Keys": keyList } } )
  ds = []
  for x in res["Responses"]["bookshelf"]:
    ds.append({k: deserializer.deserialize(v) for k, v in x.items()})
  return ds

def getBook(book):
  if(book["title"] and book["book_id"]):
    res = db_client.get_item(TableName = "bookshelf", Key = {"title" : {"S" : book["title"]}, "book_id" : {"S" : book["book_id"]}})
    if(res.get("Item")):
      ds = {k: deserializer.deserialize(v) for k, v in res.get("Item").items()}
      return ds
  #here we either weren't provided a book_id, or couldn't find the requested book_id (maybe a different edition has a spine)
  if(book["title"]):
    res = table.query(KeyConditionExpression = Key("title").eq(book["title"]))
    if(res["Items"]):
      # ds = {k: deserializer.deserialize(v) for k, v in res["Items"][0]}
      # return ds
      return res["Items"][0] #just return the 0th element
    return None

"""
title - primary_key
book_id - sort_key
data - the rest of the data to update 
"""
def updateBook(book):
  title=""
  book_id=""
  #set title and book_id, then del those attr
  if("title" in book):
    title = book["title"]
    del book["title"]
  if("book_id" in book):
    book_id = book["book_id"]
    del book["book_id"]
  
  u, e = get_update_params(book)
  response = table.update_item(
    Key={"title" : title, "book_id" : book_id},
    UpdateExpression=u,
    ExpressionAttributeValues=dict(e),
    ReturnValues="UPDATED_NEW"
  )
  return response

"""BOOKSHELF-USERS TABLE SECTION"""

def putUser(username, hashedPassword, salt, email, ip, authtoken, expiry):
  data = {
      "username" : username,
      "hashedPassword" : hashedPassword,
      "salt" : salt,
      "email" : email,
      "ip" : ip,
      "authtoken" : authtoken,
      "expiry" : expiry
  }
  print("attempting to register user " + username + " from ip " + ip) 
  try:
    res = usertable.put_item(Item=data)
    print("successfuly registered user " + username + " from ip " + ip) 
    return res
  except Exception as e:
    print(e)
    print("failed to register user " + username + " from ip " + ip) 
    return False
    
def putAuthtoken(username, authtoken, expiry):
  print("attempting to putAuthtoken for user " + username) 
  try:
    res = usertable.update_item(Key={"username" : username}, UpdateExpression="set authtoken=:a, expiry=:e", ExpressionAttributeValues={":a" : authtoken, ":e" : expiry})
    print("successfuly putAuthtoken for user " + username) 
    return res
  except Exception as e:
    print(e)
    print("failed to putAuthtoken for user " + username) 
    return False
  
def getUser(username):
  res = db_client.get_item(TableName = "bookshelf-users", Key = {"username" : {"S" :username}})
  if(len(res) > 1):
    ds = {k: deserializer.deserialize(v) for k, v in res.get("Item").items()}
    return ds
  else:
    return False

"""SHELF-IMAGES TABLE SECTION"""

def putShelfImage(filename):
  data = {
    "filename" : filename,
    "timestamp" : int(time.time())
  }
  print("attempting to put " + filename)
  try:
    res = shelftable.put_item(Item=data)
    print("successfuly stored " + filename) 
    return res
  except Exception as e:
    print(e)
    print("failed to store " + filename) 
    return False

def getAllShelfImages():
  response = shelftable.scan()
  items = response['Items']
  while 'LastEvaluatedKey' in response:
    print(response['LastEvaluatedKey'])
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response['Items'])
  return items

def delShelfImage(filename):
  try:
    shelftable.delete_item(Key={"filename":filename})
    return True
  except Exception as e:
    return False
