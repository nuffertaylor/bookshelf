"""Hardcover library -> shelves and the {found, unfound} book shape. Nothing is cached or stored."""
import json
import math
import re
from time import monotonic

from bookshelf.bookshelf import convertISBNtoISBN13
from bookshelf.hardcover_client import HardcoverError, first_me, user_graphql

PAGE_SIZE = 500
LIST_PAGE_SIZE = 100
MAX_SHELF_ROWS = 20_000

STATUSES = [
    (1, "Want to Read"),
    (2, "Currently Reading"),
    (3, "Read"),
    (4, "Paused"),
    (5, "Did Not Finish"),
]

_BOOK_FIELDS = "id title release_year contributions { contribution author { name } }"
_EDITION_FIELDS = "isbn_10 isbn_13"
_LIST_READING_FIELDS = "user_books { rating status_id last_read_date }"

SHELVES_QUERY = (
    "query { me { id "
    + " ".join(
        f"s{sid}: user_books_aggregate(where: {{status_id: {{_eq: {sid}}}}}) {{ aggregate {{ count }} }}"
        for sid, _ in STATUSES
    )
    + " lists { id name books_count } } }"
)

STATUS_SHELF_QUERY = (
    "query ($status: Int!, $limit: Int!, $offset: Int!) { me { "
    "user_books(where: {status_id: {_eq: $status}}, order_by: {id: asc}, limit: $limit, offset: $offset) { "
    "rating last_read_date book_id edition { " + _EDITION_FIELDS + " } book { " + _BOOK_FIELDS + " } } } }"
)

# TODO(live): list_books ordering/where on `me.lists` were not exercised by the Phase 0 spike
# with variables; verify against the real API.
LIST_SHELF_QUERY = (
    "query ($list: Int!, $limit: Int!, $offset: Int!) { me { "
    "lists(where: {id: {_eq: $list}}) { id name "
    "list_books(order_by: {id: asc}, limit: $limit, offset: $offset) { "
    "book_id edition { " + _EDITION_FIELDS + " } book { " + _BOOK_FIELDS + " } "
    + _LIST_READING_FIELDS + " } } } }"
)
LIST_SHELF_WITHOUT_READING_QUERY = LIST_SHELF_QUERY.replace(_LIST_READING_FIELDS, "")
LIST_READING_QUERY = (
    "query ($ids: [Int!]!) { me { user_books(where: {book_id: {_in: $ids}}, "
    "order_by: {id: asc}) { book_id rating last_read_date } } }"
)


class ShelfNotFound(Exception):
    pass


def _count(me, alias):
    agg = (me.get(alias) or {}).get("aggregate") or {}
    return int(agg.get("count") or 0)


def get_shelves(db, username):
    data = user_graphql(db, username, SHELVES_QUERY, {})
    me = first_me(data)
    if not me:
        return []
    shelves = [{"id": f"status:{sid}", "name": name, "count": _count(me, f"s{sid}")} for sid, name in STATUSES]
    for lst in me.get("lists") or []:
        shelves.append({"id": f"list:{lst['id']}", "name": lst.get("name") or "", "count": int(lst.get("books_count") or 0)})
    return shelves


def author_name(book):
    """First contribution with contribution == "Author", else the first entry."""
    contributions = [c for c in (book.get("contributions") or []) if isinstance(c, dict) and c.get("author")]
    if not contributions:
        return ""
    for c in contributions:
        if c.get("contribution") == "Author":
            return c["author"].get("name") or ""
    return contributions[0]["author"].get("name") or ""


def _rating_to_str(rating):
    """Hardcover ratings are floats (4.0, 3.5); Goodreads ones are int strings. Round half up."""
    if rating is None:
        return ""
    return str(int(float(rating) + 0.5))


def map_book(book, edition, rating, last_read_date):
    edition = edition or {}
    isbn10 = edition.get("isbn_10") or ""
    isbn13 = edition.get("isbn_13") or convertISBNtoISBN13(isbn10) or None
    year = book.get("release_year")
    return {
        "title": book.get("title") or "",
        "author": author_name(book),
        "isbn": isbn10,
        "isbn13": isbn13,
        "pubDate": str(year) if year else "",
        "user_rating": _rating_to_str(rating),
        "user_read_at": last_read_date or "",
        "hardcover_book_id": book["id"],
    }


def _parse_shelf_id(shelf):
    kind, _, raw = str(shelf).partition(":")
    if kind not in ("status", "list") or not raw.isdigit():
        raise ShelfNotFound("unknown shelf")
    value = int(raw)
    if kind == "status" and value not in dict(STATUSES):
        raise ShelfNotFound("unknown shelf")
    return kind, value


def _rows_status(me):
    for ub in me.get("user_books") or []:
        yield ub.get("book"), ub.get("edition"), ub.get("rating"), ub.get("last_read_date")


def _list_entries(me):
    lists = me.get("lists") or []
    if not lists:
        raise ShelfNotFound("unknown shelf")
    return lists[0].get("list_books") or []


def _rows_list(me, reading_by_book=None):
    for lb in _list_entries(me):
        uds = lb.get("user_books") or []
        ub = reading_by_book.get(lb.get("book_id"), {}) if reading_by_book is not None else (uds[0] if uds else {})
        yield lb.get("book"), lb.get("edition"), ub.get("rating"), ub.get("last_read_date")


def _list_reading_by_book(db, username, me):
    ids = list(dict.fromkeys(row["book_id"] for row in _list_entries(me) if row.get("book_id") is not None))
    if not ids:
        return {}
    data = user_graphql(db, username, LIST_READING_QUERY, {"ids": ids})
    reading_by_book = {}
    for row in (first_me(data) or {}).get("user_books") or []:
        reading_by_book.setdefault(row["book_id"], row)
    return reading_by_book


LIST_PROBE_FIELDS = {
    "edition": "edition { " + _EDITION_FIELDS + " }",
    "book": "book { " + _BOOK_FIELDS + " }",
    "user_books": _LIST_READING_FIELDS,
}


def probe_list_book_ids(db, username, shelf, field=None):
    kind, value = _parse_shelf_id(shelf)
    if kind != "list":
        raise ShelfNotFound("unknown list")
    extra_fields = LIST_PROBE_FIELDS.get(field, "")
    query = (
        "query ($list: Int!, $limit: Int!) { me { lists(where: {id: {_eq: $list}}) { id "
        "list_books(order_by: {id: asc}, limit: $limit, offset: 0) { book_id "
        + extra_fields + " } } } }"
    )
    data = user_graphql(db, username, query, {"list": value, "limit": LIST_PAGE_SIZE})
    lists = (first_me(data) or {}).get("lists") or []
    if not lists:
        raise ShelfNotFound("unknown list")
    return [row["book_id"] for row in lists[0].get("list_books") or []]


def get_shelf_books(db, username, shelf):
    """All books on a status shelf ("status:3") or the user's own custom list ("list:456"), paged
    up to 20,000 rows. Raises ShelfNotFound for a bad/unknown shelf id."""
    kind, value = _parse_shelf_id(shelf)
    query, var_name, extract = (
        (STATUS_SHELF_QUERY, "status", _rows_status) if kind == "status" else (LIST_SHELF_QUERY, "list", _rows_list)
    )
    books = []
    page_size = LIST_PAGE_SIZE if kind == "list" else PAGE_SIZE
    for offset in range(0, MAX_SHELF_ROWS, page_size):
        variables = {var_name: value, "limit": page_size, "offset": offset}
        started = monotonic()
        try:
            data = user_graphql(db, username, query, variables)
        except HardcoverError as exc:
            print(
                f"hardcover shelf page failed: kind={kind} offset={offset} limit={page_size} "
                f"status={exc.status} elapsed_ms={round((monotonic() - started) * 1000)}"
            )
            if query != LIST_SHELF_QUERY or exc.status != 408:
                raise
            query = LIST_SHELF_WITHOUT_READING_QUERY
            data = user_graphql(db, username, query, variables)
        me = first_me(data) or {}
        rows = (
            _rows_list(me, _list_reading_by_book(db, username, me))
            if query == LIST_SHELF_WITHOUT_READING_QUERY
            else extract(me)
        )
        page = 0
        for book, edition, rating, last_read in rows:
            page += 1
            if book and book.get("id") is not None:
                books.append(map_book(book, edition, rating, last_read))
        if page < page_size:
            break
    return books


# ---- catalog search (contribute flow) ----------------------------------------------------------

SEARCH_MIN_LEN = 3
SEARCH_MAX_LEN = 200
SEARCH_PER_PAGE = 10

# Typesense defaults are used (no fields/weights). TODO(live): ranking tuning needs a real token;
# try fields/weights (e.g. higher author_names weight) on "project hail mary", "hail mary andy weir"
# and compare. Not done yet (plan section 5, open item on ranking).
SEARCH_QUERY = (
    "query ($q: String!, $n: Int!) { search(query: $q, query_type: \"Book\", per_page: $n, page: 1) { results } }"
)


def _isbn_kind(value):
    v = str(value or "").strip().replace("-", "").upper()
    if len(v) == 13 and v.isdigit():
        return 13, v
    if len(v) == 10 and v[:9].isdigit() and (v[9].isdigit() or v[9] == "X"):
        return 10, v
    return None, None


def _pick_isbns(isbns):
    isbn10 = isbn13 = ""
    for raw in isbns if isinstance(isbns, list) else []:
        kind, v = _isbn_kind(raw)
        if kind == 10 and not isbn10:
            isbn10 = v
        elif kind == 13 and not isbn13:
            isbn13 = v
    if isbn10 and not isbn13:
        isbn13 = convertISBNtoISBN13(isbn10) or ""
    return isbn10, isbn13


def _hits(data):
    search = data.get("search") if isinstance(data, dict) else None
    results = search.get("results") if isinstance(search, dict) else None
    if isinstance(results, str):
        try:
            results = json.loads(results)
        except ValueError:
            return []
    hits = results.get("hits") if isinstance(results, dict) else None
    return hits if isinstance(hits, list) else []


MAX_ID = 2**63 - 1  # fits a signed 64-bit column


def _parse_id(value):
    """Strict ASCII-digit id that fits a signed 64-bit int, else None."""
    if isinstance(value, bool):
        return None
    s = str(value).strip()
    if len(s) > 19 or not re.fullmatch(r"[0-9]+", s):
        return None
    n = int(s)
    return n if n <= MAX_ID else None


def _year_str(year):
    """release_year as a clean year string ("1965"), or "" when absent/non-numeric."""
    if isinstance(year, bool):
        return ""
    if isinstance(year, float):
        year = int(year) if math.isfinite(year) and year.is_integer() else None
    elif isinstance(year, str):
        m = re.fullmatch(r"([0-9]{1,4})(?:\.0+)?", year.strip())
        year = int(m.group(1)) if m else None
    elif not isinstance(year, int):
        year = None
    return str(year) if year and 0 < year <= 9999 else ""


def _text(value):
    return value if isinstance(value, str) else ""


def _normalize_hit(hit):
    doc = hit.get("document") if isinstance(hit, dict) else None
    if not isinstance(doc, dict):
        return None
    book_id = _parse_id(doc.get("id"))
    if book_id is None:
        return None
    author = author_name(doc)
    if not author:
        names = doc.get("author_names")
        author = names[0] if isinstance(names, list) and names and isinstance(names[0], str) else ""
    isbn, isbn13 = _pick_isbns(doc.get("isbns"))
    return {
        "hardcover_book_id": book_id,
        "title": _text(doc.get("title")),
        "subtitle": _text(doc.get("subtitle")),
        "author": author,
        "pubDate": _year_str(doc.get("release_year")),
        "isbn": isbn,
        "isbn13": isbn13,
        "already_uploaded": False,
    }


def search_books(db, username, query):
    """Search Hardcover's public catalog as `username`. Raises ValueError for a bad query.
    Results are neither logged nor stored."""
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    query = query.strip()
    if not SEARCH_MIN_LEN <= len(query) <= SEARCH_MAX_LEN:
        raise ValueError(f"query must be {SEARCH_MIN_LEN} to {SEARCH_MAX_LEN} characters")
    data = user_graphql(db, username, SEARCH_QUERY, {"q": query, "n": SEARCH_PER_PAGE}, required_scope="read:catalog")
    results = [r for r in (_normalize_hit(h) for h in _hits(data)) if r]
    if results:
        uploaded = set(db.get_uploaded_hardcover_ids(username, [r["hardcover_book_id"] for r in results]))
        for r in results:
            r["already_uploaded"] = r["hardcover_book_id"] in uploaded
    return results
