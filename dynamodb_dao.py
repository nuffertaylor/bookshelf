import boto3
from boto3.dynamodb.types import TypeDeserializer

region = "us-east-1"
regionEndpoint = "https://dynamodb."+ region + ".amazonaws.com"
dynamodb = boto3.resource('dynamodb', endpoint_url=regionEndpoint)
db_client = boto3.client("dynamodb", region)
table = dynamodb.Table('bookshelf')
deserializer = TypeDeserializer()

def split_list(a_list):
  #stackoverflow.com/questions/752308
  half = len(a_list)//2
  return a_list[:half], a_list[half:]

def putBook(title, book_id, pubDate = "", author = "", isbn = "", isbn13 = "", fileName = "", dimensions = "", domColor = "", genre = ""):

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
      "genre" : genre
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
  # if(len(books) > 99): #max batch request size is 100. so we'll recursively split the list if it's too big
  #   a, b = split_list(books)
  #   return getBookBatch(a) + getBookBatch(b)
  for book in books:
    key = {"title" : {"S" : book["title"]}, "book_id" : {"S" : book["book_id"]}}
    keyList.append(key)
  res = db_client.batch_get_item( RequestItems = { "bookshelf": { "Keys": keyList } } )
  ds = []
  for x in res["Responses"]["bookshelf"]:
    ds.append({k: deserializer.deserialize(v) for k, v in x.items()})
  return ds
  

def getBook(book):
  res = db_client.get_item(TableName = "bookshelf", Key = {"title" : {"S" : book["title"]}, "book_id" : {"S" : book["book_id"]}})
  ds = {k: deserializer.deserialize(v) for k, v in res.get("Item").items()}
  return ds