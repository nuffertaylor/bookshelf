import os
import feedparser
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.bookshelf import convertISBNtoISBN13

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


def which_books_found(db, bookList):
    all_spines = db.get_spines_batch_by_title_author(bookList)

    spine_lookup = {}
    book_id_lookup = {}
    for spine in all_spines:
        key = (spine["title"].lower().strip() if spine["title"] else "", spine["author"].lower().strip() if spine["author"] else "")
        if key not in spine_lookup:
            spine_lookup[key] = []
        spine_lookup[key].append(spine)
        bid = str(spine.get("book_id", ""))
        if bid:
            if bid not in book_id_lookup:
                book_id_lookup[bid] = []
            book_id_lookup[bid].append(spine)

    unfound = []
    found = []

    for b in bookList:
        key = (b["title"].lower().strip() if b["title"] else "", b["author"].lower().strip() if b["author"] else "")
        spines = spine_lookup.get(key, []) or book_id_lookup.get(str(b.get("book_id", "")), [])

        if len(spines) == 0:
            unfound.append(b)
        else:
            matching_book_id = []
            other_spines = []
            for spine in spines:
                spine_copy = spine.copy()
                spine_copy.update(b)
                if str(spine_copy["book_id"]) == str(b["book_id"]):
                    matching_book_id.append(spine_copy)
                else:
                    other_spines.append(spine_copy)
            found.append(matching_book_id + other_spines)

    return found, unfound


def lambda_handler(event, context):
    db = _get_db()
    books = get_books_from_shelf(event["userid"], event["shelfname"])
    print("looking for " + str(len(books)) + " books")
    found, unfound = which_books_found(db, books)
    print("found images for " + str(len(found)) + " books")
    return {
        "statusCode": 200,
        "body": {"found": found, "unfound": unfound},
    }
