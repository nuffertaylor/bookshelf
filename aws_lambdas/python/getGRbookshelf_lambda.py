from cockroachdb_dao import CockroachDAO
import feedparser
import os
db = CockroachDAO(os.getenv('DATABASE_URL'))

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
  books = []
  page_counter = 1
  while(True):
    parsed_rss = feedparser.parse(rss_url + "&page=" + str(page_counter))
    if(len(parsed_rss["entries"]) == 0): break
    for entry in parsed_rss["entries"]:
      book = {"book_id" : entry["book_id"], 
              "title" : entry["title"], 
              "pubDate" : entry["book_published"],
              "author" : entry["author_name"],
              "isbn" : entry["isbn"],
              "isbn13" : convertISBNtoISBN13(entry["isbn"]),
              "user_read_at" : entry["user_read_at"],
              "average_rating" : entry["average_rating"],
              "user_rating" : entry["user_rating"]
              }
      books.append(book)
    page_counter += 1
  return books

def which_books_found(bookList, foundBooks):
  #return a list, the edited bookList which only contains the books not found in foundBooks
  unfound = []
  found = []
  for b in bookList:
    foundBool = False
    # first loop checks for book_id
    for f in foundBooks:
      if(str(b["book_id"]) == str(f["book_id"])):
        foundBool = True
        f.update(b)
        found.append(f)
        break
    # second loop checks for title match
    # TODO: it should make sure title AND author match
    if(not foundBool):
      for f in foundBooks:
        if(b["title"] == f["title"]):
          foundBool = True
          f.update(b)
          found.append(f)
          break
    if(not foundBool):
      unfound.append(b)
  return found, unfound

def getGRbookshelf(userid, shelfname):
  #TODO: Do verification on userid. Ensure it is only numbers.
  #TODO: If it isn't only numbers, it may be a profile URL. Edit the input and see if we can get a valid user_id this way. If not, return fail.
  books = get_books_from_shelf(userid, shelfname)
  print("looking for " + str(len(books)) + " books")
  batch = db.get_book_batch(books)
  print("found images for " + str(len(batch)) + " books")
  found, unfound = which_books_found(books, batch)
  return {
    "found" : found,
    "unfound" : unfound
  }
  
def lambda_handler(event, context):
  return {
    'statusCode': 200,
    'body': getGRbookshelf(event["userid"], event["shelfname"])
  }

# zip -r lambda.zip .
# aws lambda update-function-code --function-name getGRbookshelf --zip-file fileb://~/projects/bookshelf/aws_lambdas/python/lambda.zip