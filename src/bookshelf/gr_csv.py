import csv
import io
import re

REQUIRED_COLUMNS = {"Book Id", "Title", "Author", "Exclusive Shelf", "Bookshelves"}


class GoodreadsCsvError(ValueError):
    pass


def _clean_isbn(value):
    # Goodreads exports ISBNs as Excel-safe formulas, e.g. ="1506711987" (empty is =""")
    return re.sub(r'[^0-9Xx]', '', value or "")


def _rows(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("﻿"), newline=""))
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise GoodreadsCsvError("Not a Goodreads library export, missing columns: " + ", ".join(sorted(missing)))
    return reader


def _shelves_of(row):
    shelves = [s.strip() for s in row["Bookshelves"].split(",") if s.strip()]
    exclusive = row["Exclusive Shelf"].strip()
    if exclusive and exclusive not in shelves:
        shelves.append(exclusive)
    return shelves


def _book_from_row(row, convert_isbn):
    isbn = _clean_isbn(row.get("ISBN"))
    isbn13 = _clean_isbn(row.get("ISBN13")) or convert_isbn(isbn)
    return {
        "book_id": row["Book Id"].strip(),
        "title": row["Title"],
        "pubDate": row.get("Year Published", ""),
        "author": row["Author"],
        "isbn": isbn,
        "isbn13": isbn13 or None,
        "user_read_at": row.get("Date Read", ""),
        "average_rating": row.get("Average Rating", ""),
        "user_rating": row.get("My Rating", ""),
    }


def list_shelves(csv_text):
    """Return [{"name", "count"}] for every shelf in the export, largest first."""
    counts = {}
    for row in _rows(csv_text):
        for shelf in _shelves_of(row):
            counts[shelf] = counts.get(shelf, 0) + 1
    return [{"name": n, "count": c} for n, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def books_on_shelf(csv_text, shelf, convert_isbn):
    """Books on the given shelf, in the same dict shape the old RSS fetch produced."""
    return [_book_from_row(row, convert_isbn) for row in _rows(csv_text) if shelf in _shelves_of(row)]
