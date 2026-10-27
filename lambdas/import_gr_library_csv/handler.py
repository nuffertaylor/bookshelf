import os

from bookshelf.bookshelf import convertISBNtoISBN13, which_books_found
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.gr_csv import GoodreadsCsvError, books_on_shelf, list_shelves
from bookshelf.http import http_result, parse_event

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    """
    Replacement for getGRBookshelf now that Goodreads has removed its RSS feeds.
    Takes the text of a Goodreads library export (My Books > Import and export).
      - {"csv": ...}                  -> {"shelves": [{"name", "count"}]}  (shelf options)
      - {"csv": ..., "shelf": "2020"} -> {"found": [...], "unfound": [...]} (same as getGRBookshelf)
    """
    event = parse_event(event)
    csv_text = event.get("csv")
    if not csv_text:
        return http_result(400, {"error": "csv is required"})

    try:
        shelf = event.get("shelf")
        if not shelf:
            return http_result(200, {"shelves": list_shelves(csv_text)})

        books = books_on_shelf(csv_text, shelf, convertISBNtoISBN13)
    except GoodreadsCsvError as e:
        return http_result(400, {"error": str(e)})

    print("looking for " + str(len(books)) + " books")
    found, unfound = which_books_found(_get_db(), books)
    print("found images for " + str(len(found)) + " books")
    return http_result(200, {"found": found, "unfound": unfound})
