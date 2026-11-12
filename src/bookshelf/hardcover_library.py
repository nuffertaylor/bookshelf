"""Hardcover library -> shelves and the {found, unfound} book shape. Nothing is cached or stored."""
from bookshelf.bookshelf import convertISBNtoISBN13
from bookshelf.hardcover_client import first_me, user_graphql

PAGE_SIZE = 500
MAX_PAGES = 40  # hard stop: 20,000 books

STATUSES = [
    (1, "Want to Read"),
    (2, "Currently Reading"),
    (3, "Read"),
    (4, "Paused"),
    (5, "Did Not Finish"),
]

_BOOK_FIELDS = "id title release_year contributions { contribution author { name } }"
_EDITION_FIELDS = "isbn_10 isbn_13"

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
    "user_books { rating status_id last_read_date } } } } }"
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


def _rows_list(me):
    lists = me.get("lists") or []
    if not lists:
        raise ShelfNotFound("unknown shelf")
    for lb in lists[0].get("list_books") or []:
        uds = lb.get("user_books") or []
        ub = uds[0] if uds else {}
        yield lb.get("book"), lb.get("edition"), ub.get("rating"), ub.get("last_read_date")


def get_shelf_books(db, username, shelf):
    """All books on a status shelf ("status:3") or the user's own custom list ("list:456"), paged
    500 at a time. Raises ShelfNotFound for a bad/unknown shelf id."""
    kind, value = _parse_shelf_id(shelf)
    query, var_name, extract = (
        (STATUS_SHELF_QUERY, "status", _rows_status) if kind == "status" else (LIST_SHELF_QUERY, "list", _rows_list)
    )
    books = []
    offset = 0
    for _ in range(MAX_PAGES):
        data = user_graphql(db, username, query, {var_name: value, "limit": PAGE_SIZE, "offset": offset})
        me = first_me(data) or {}
        page = 0
        for book, edition, rating, last_read in extract(me):
            page += 1
            if book and book.get("id") is not None:
                books.append(map_book(book, edition, rating, last_read))
        if page < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return books
