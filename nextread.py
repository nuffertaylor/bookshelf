import feedparser
import random

def get_books_from_shelf(userid, shelfname):
  rss_url = "https://www.goodreads.com/review/list_rss/" + userid + "?shelf=" + shelfname
  parsed_rss = feedparser.parse(rss_url)
  return parsed_rss["entries"]

books = get_books_from_shelf("119763485", "to-read")
bookIndex = random.randint(0, len(books))
print(books[bookIndex]["title"])