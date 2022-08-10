import feedparser
import random

def get_books_from_shelf(userid, shelfname):
  rss_url = "https://www.goodreads.com/review/list_rss/" + userid + "?shelf=" + shelfname
  parsed_rss = feedparser.parse(rss_url)
  return parsed_rss["entries"]

books = get_books_from_shelf("119763485", "2022")
out = "title, author, author gender, genre, year, numpages, avg rating, user rating\n"
for b in books:
  out += "\"" + b["title"] + "\"," + b["author_name"] + ", , ," + b["book_published"] + "," + b["num_pages"] + "," + b["average_rating"] + "," + b["user_rating"] + "\n"
print(out)