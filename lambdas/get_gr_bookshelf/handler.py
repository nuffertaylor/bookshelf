import os

import feedparser
from bookshelf.bookshelf import convertISBNtoISBN13, which_books_found
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.http import http_result, parse_event

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def get_books_from_shelf(userid, shelfname):
    rss_url = "https://www.goodreads.com/review/list_rss/" + userid + "?shelf=" + shelfname
    books = []
    page_counter = 1
    while True:
        parsed_rss = feedparser.parse(rss_url + "&page=" + str(page_counter))
        if len(parsed_rss["entries"]) == 0:
            break
        for entry in parsed_rss["entries"]:
            book = {
                "book_id": entry["book_id"],
                "title": entry["title"],
                "pubDate": entry["book_published"],
                "author": entry["author_name"],
                "isbn": entry["isbn"],
                "isbn13": convertISBNtoISBN13(entry["isbn"]),
                "user_read_at": entry["user_read_at"],
                "average_rating": entry["average_rating"],
                "user_rating": entry["user_rating"],
            }
            books.append(book)
        page_counter += 1
    return books


def lambda_handler(event, context):
    event = parse_event(event)
    db = _get_db()
    books = get_books_from_shelf(event["userid"], event["shelfname"])
    print("looking for " + str(len(books)) + " books")
    found, unfound = which_books_found(db, books)
    print("found images for " + str(len(found)) + " books")
    return http_result(200, {"found": found, "unfound": unfound})
