from dynamodb_dao import getBookBatch
import feedparser

def check_digit_13(isbn):
  assert len(isbn) == 12
  sum = 0
  for i in range(len(isbn)):
    c = int(isbn[i])
    if i % 2: w = 3
    else: w = 1
    sum += w * c
  r = 10 - (sum % 10)
  if r == 10: return '0'
  else: return str(r)

def convertISBNtoISBN13(isbn):
  if(len(isbn) == 13): return isbn
  if(len(isbn) != 10 or not isbn.isdigit()): return None
  # assert len(isbn) == 10
  prefix = "978" + isbn[:-1]
  check = check_digit_13(prefix)
  return prefix + check

def get_books_from_shelf(userid, shelfname):
  rss_url = "https://www.goodreads.com/review/list_rss/" + userid + "?shelf=" + shelfname
  parsed_rss = feedparser.parse(rss_url)
  books = []
  for entry in parsed_rss["entries"]:
    book = {"book_id" : entry["book_id"], 
            "title" : entry["title"], 
            "pubDate" : entry["book_published"],
            "author" : entry["author_name"],
            "isbn" : entry["isbn"],
            "isbn13" : convertISBNtoISBN13(entry["isbn"])
            }
    books.append(book)
  return books

def whichBooksFound(bookList, foundBooks):
  #return a list, the edited bookList which only contains the books not found in foundBooks
  unfound = []
  for b in bookList:
    found = False
    for f in foundBooks:
      if(b["title"] == f["title"]):
        found = True
        break
    if(not found):
      unfound.append(b)
  return unfound

def getGRbookshelf(userid, shelfname):
  books = get_books_from_shelf(userid, shelfname)
  print("looking for " + str(len(books)) + " books")
  batch = getBookBatch(books)
  print("found images for " + str(len(batch)) + " books")
  unfound = whichBooksFound(books, batch)
  return {
    "found" : batch,
    "unfound" : unfound
  }
  
def lambda_handler(event, context):
  return {
    'statusCode': 200,
    'body': getGRbookshelf(event["userid"], event["shelfname"])
  }
