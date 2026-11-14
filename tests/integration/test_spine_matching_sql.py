"""Spine matching against a real database (Postgres or CockroachDB).

The matching rules live partly in SQL, so this runs the real DAO method rather than the fake. Set
TEST_DATABASE_URL to choose the database (default: the docker-compose Postgres). Skipped when nothing is
reachable. Each test gets a throwaway schema that is dropped afterwards, so no real data is touched.
"""
import os
import uuid

import pytest

import psycopg2
from bookshelf.bookshelf import which_books_found
from bookshelf.dao.cockroachdb_dao import CockroachDAO

DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:dev@localhost:5432/bookshelf")

BOOKSHELF_DDL = """
CREATE TABLE bookshelf (
  upload_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id INT, title TEXT NOT NULL, author TEXT, dimensions TEXT NOT NULL, domColor TEXT,
  fileName TEXT UNIQUE NOT NULL, genre TEXT, isbn TEXT, isbn13 TEXT, pubDate TEXT,
  submitter TEXT NOT NULL, rating INT, flagged BOOLEAN, timestamp INT, hardcover_book_id INT
)
"""


@pytest.fixture
def dao():
    name = "t_" + uuid.uuid4().hex[:12]
    try:
        admin = psycopg2.connect(DB_URL, connect_timeout=3)
    except psycopg2.OperationalError:
        pytest.skip("no database reachable (set TEST_DATABASE_URL)")
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f"CREATE SCHEMA {name}")
    d = CockroachDAO.__new__(CockroachDAO)  # skip __init__: it would connect without our search_path
    d.conn = psycopg2.connect(DB_URL, options=f"-c search_path={name}", connect_timeout=3)
    d.conn.autocommit = True
    with d.conn.cursor() as cur:
        cur.execute(BOOKSHELF_DDL)
    d.conn.autocommit = False
    try:
        yield d
    finally:
        d.conn.close()
        with admin.cursor() as cur:
            cur.execute(f"DROP SCHEMA {name} CASCADE")
        admin.close()


def add(dao, title, author, *, book_id=None, hardcover_book_id=None, timestamp=None):
    """Insert a spine; returns its file name, which identifies it in results (which_books_found copies the
    requested book's title and book_id over each matched spine, so those can't identify the stored row)."""
    file_name = uuid.uuid4().hex + ".jpg"
    assert dao.exec_statement(
        "INSERT INTO bookshelf (book_id, title, author, dimensions, fileName, submitter, timestamp, hardcover_book_id) "
        "VALUES (%s, %s, %s, '1 x 2 x 3', %s, 'tester', %s, %s)",
        (book_id, title, author, file_name, timestamp, hardcover_book_id))
    return file_name


def files(found_entry):
    return [s["fileName"] for s in found_entry]


def test_hardcover_title_matches_goodreads_series_title(dao):
    wanted = add(dao, "Words of Radiance (The Stormlight Archive, #2)", "Brandon Sanderson", book_id=17332218)
    add(dao, "Unrelated", "Someone Else", book_id=5)
    found, unfound = which_books_found(dao, [{"hardcover_book_id": 374131, "title": "Words of Radiance", "author": "Brandon Sanderson"}])
    assert unfound == [] and files(found[0]) == [wanted]


def test_goodreads_series_title_matches_plain_stored_title(dao):
    wanted = add(dao, "Red Country", "Joe Abercrombie", hardcover_book_id=297006)
    found, unfound = which_books_found(dao, [{"book_id": "99", "title": "Red Country (Standalone, #6)", "author": "Joe Abercrombie"}])
    assert unfound == [] and files(found[0]) == [wanted]


def test_curly_quotes_case_and_repeated_spaces(dao):
    add(dao, "The Book That Wouldn't Burn", "Mark Lawrence", book_id=1)
    add(dao, "The Utterly Uninteresting Tales", "Drew Hayes", book_id=2)
    found, unfound = which_books_found(dao, [
        {"hardcover_book_id": 684408, "title": "The Book That Wouldn’t Burn", "author": "MARK  LAWRENCE"},
        {"hardcover_book_id": 438803, "title": "the utterly uninteresting tales", "author": "Drew  Hayes"},
    ])
    assert unfound == [] and len(found) == 2


def test_different_books_and_authors_do_not_match(dao):
    add(dao, "Dune Messiah (Dune Chronicles, #2)", "Frank Herbert", book_id=1)
    add(dao, "The Hunter", "Richard Stark", book_id=2)
    books = [{"hardcover_book_id": 312460, "title": "Dune", "author": "Frank Herbert"},
             {"hardcover_book_id": 314391, "title": "The Hunter", "author": "Someone Else"}]
    found, unfound = which_books_found(dao, books)
    assert found == [] and unfound == books


def test_everything_the_old_exact_rule_matched_still_matches(dao):
    pairs = [("Dune", "Frank Herbert"), ("Solaris", "Stanisław Lem"), ("Foundation (Foundation, #1)", "Isaac Asimov"),
             ("A Title", "An Author"), ("ÉCOLE du soir", "Marie Dupré")]
    for t, a in pairs:
        add(dao, t, a, book_id=1)
    # old rule: LOWER(TRIM(title)) = LOWER(TRIM(requested)) AND the same for author, case-insensitive
    books = [{"hardcover_book_id": i + 1, "title": f"  {t.upper()} ", "author": a.upper()} for i, (t, a) in enumerate(pairs)]
    found, unfound = which_books_found(dao, books)
    assert unfound == [] and len(found) == len(pairs)


def test_equal_matches_come_back_in_a_stable_order_oldest_first_nulls_last(dao):
    add(dao, "Dune", "Frank Herbert", book_id=11, timestamp=300)
    add(dao, "Dune", "Frank Herbert", book_id=12, timestamp=100)
    add(dao, "Dune", "Frank Herbert", book_id=13, timestamp=None)
    add(dao, "Dune", "Frank Herbert", book_id=14, timestamp=200)
    book = {"hardcover_book_id": 312460, "title": "Dune", "author": "Frank Herbert"}
    for _ in range(3):  # same answer every time
        found, _ = which_books_found(dao, [book])
        assert [s["book_id"] for s in found[0]] == [12, 14, 11, 13]


def test_id_matches_still_work_without_any_title_match(dao):
    add(dao, "Totally Different Title", "Nobody", book_id=7, hardcover_book_id=99)
    found, unfound = which_books_found(dao, [
        {"hardcover_book_id": 99, "title": "Dune", "author": "Frank Herbert"},
        {"book_id": "7", "title": "Dune", "author": "Frank Herbert"}])
    assert unfound == [] and len(found) == 2


def test_blank_authors_behave_as_before_blank_matches_blank_but_null_matches_nothing(dao):
    # Characterises the existing SQL: LOWER(TRIM('')) = LOWER(TRIM('')) is true, while NULL = anything is not.
    add(dao, "Dune", None, book_id=1)
    solaris = add(dao, "Solaris", "", book_id=2)
    found, unfound = which_books_found(dao, [{"hardcover_book_id": 1, "title": "Dune", "author": ""},
                                             {"hardcover_book_id": 2, "title": "Solaris", "author": ""}])
    assert [files(f) for f in found] == [[solaris]]
    assert [b["title"] for b in unfound] == ["Dune"]


def test_empty_book_list(dao):
    assert dao.get_spines_batch_by_title_author([]) == []
