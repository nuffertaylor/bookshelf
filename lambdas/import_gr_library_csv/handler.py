import os

from bookshelf.bookshelf import convertISBNtoISBN13, which_books_found
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.gr_csv import CsvTooLargeError, GoodreadsCsvError, books_on_shelf, list_shelves
from bookshelf.http import http_result, parse_event

MAX_CSV_CHARS = 4_000_000
MAX_ROWS = 20_000

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
    try:
        event = parse_event(event)
    except ValueError:  # includes json.JSONDecodeError and UnicodeDecodeError
        return http_result(400, {"error": "request body must be JSON"})
    if not isinstance(event, dict):
        return http_result(400, {"error": "request body must be a JSON object"})

    csv_text = event.get("csv")
    if not csv_text:
        return http_result(400, {"error": "csv is required"})
    if not isinstance(csv_text, str):
        return http_result(400, {"error": "csv must be a string"})
    # TODO: files over MAX_CSV_CHARS are rejected. If real users hit this, add an S3 presigned-upload
    # path (client PUTs to S3, Lambda reads from S3, lifecycle rule deletes after a day), or some
    # other solution. Stored exports contain private reviews and notes, so that needs a privacy review.
    if len(csv_text) > MAX_CSV_CHARS:
        return http_result(413, {"error": "CSV is larger than 4 MB. Large-file support is not available yet."})

    try:
        shelf = event.get("shelf")
        if not shelf:
            return http_result(200, {"shelves": list_shelves(csv_text, MAX_ROWS)})
        if not isinstance(shelf, str):
            return http_result(400, {"error": "shelf must be a string"})

        books = books_on_shelf(csv_text, shelf, convertISBNtoISBN13, MAX_ROWS)
    except CsvTooLargeError as e:
        return http_result(413, {"error": str(e)})
    except GoodreadsCsvError as e:
        return http_result(400, {"error": str(e)})

    if not books:
        # A shelf that exists always has at least one book, so empty means the shelf name is unknown.
        return http_result(404, {"error": f"shelf '{shelf}' not found in this export"})

    print("looking for " + str(len(books)) + " books")
    found, unfound = which_books_found(_get_db(), books)
    print("found images for " + str(len(found)) + " books")
    return http_result(200, {"found": found, "unfound": unfound})
