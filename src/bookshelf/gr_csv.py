import csv
import io
import re

REQUIRED_COLUMNS = {"Book Id", "Title", "Author", "Exclusive Shelf", "Bookshelves"}


class GoodreadsCsvError(ValueError):
    pass


class CsvTooLargeError(GoodreadsCsvError):
    pass


def _clean_isbn(value):
    # Goodreads exports ISBNs as Excel-safe formulas, e.g. ="1506711987" (empty is =""")
    # Spreadsheet-mangled values (e.g. 9.78E+12) must not turn into garbage digits, so only a
    # well-formed ISBN-10 (with a valid check digit) or ISBN-13 survives; anything else is "".
    cleaned = re.sub(r'[^0-9Xx]', '', value or "").upper()
    if len(cleaned) == 13 and cleaned.isdigit():
        return cleaned
    if len(cleaned) == 10 and re.fullmatch(r'[0-9]{9}[0-9X]', cleaned) and _isbn10_valid(cleaned):
        return cleaned
    return ""


def _isbn10_valid(isbn):
    total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(isbn))
    return total % 11 == 0


def _rows(csv_text, max_rows=None):
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("﻿"), newline=""))
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise GoodreadsCsvError("Not a Goodreads library export, missing columns: " + ", ".join(sorted(missing)))
    for count, row in enumerate(reader, start=1):
        if max_rows is not None and count > max_rows:
            raise CsvTooLargeError("CSV has more than " + str(max_rows) + " rows.")
        yield row


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
        # RSS book_published was the original year (seed data: Ender's Game = 1985), so prefer that
        "pubDate": row.get("Original Publication Year") or row.get("Year Published", ""),
        "author": row["Author"],
        "isbn": isbn,
        "isbn13": isbn13 or None,
        "user_read_at": row.get("Date Read", ""),
        "average_rating": row.get("Average Rating", ""),
        "user_rating": row.get("My Rating", ""),
    }


def list_shelves(csv_text, max_rows=None):
    """Return [{"name", "count"}] for every shelf in the export, largest first."""
    counts = {}
    for row in _rows(csv_text, max_rows):
        for shelf in _shelves_of(row):
            counts[shelf] = counts.get(shelf, 0) + 1
    return [{"name": n, "count": c} for n, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def books_on_shelf(csv_text, shelf, convert_isbn, max_rows=None):
    """Books on the given shelf, in the same dict shape the old RSS fetch produced."""
    books = []
    seen = set()
    for row in _rows(csv_text, max_rows):
        if shelf not in _shelves_of(row):
            continue
        book_id = row["Book Id"].strip()
        if book_id in seen:
            continue
        seen.add(book_id)
        books.append(_book_from_row(row, convert_isbn))
    return books
