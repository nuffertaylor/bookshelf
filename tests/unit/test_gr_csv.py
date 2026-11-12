import pytest

from bookshelf.bookshelf import convertISBNtoISBN13
from bookshelf.gr_csv import GoodreadsCsvError, books_on_shelf, list_shelves

HEADER = ('Book Id,Title,Author,Author l-f,Additional Authors,ISBN,ISBN13,My Rating,Publisher,Binding,'
          'Number of Pages,Year Published,Original Publication Year,Date Read,Date Added,Bookshelves,'
          'Bookshelves with positions,Exclusive Shelf,My Review,Spoiler,Private Notes,Read Count,Owned Copies\n')
CSV = (HEADER
       + '1,"Berserk, Vol. 42 (Berserk, #42)",Kentaro Miura,"Miura, Kentaro",,"=""""","=""""",3.0,X,P,192,2025,2023,2026/10/26,2026/10/26,"2026, manga","",read,,,,1,0\n'
       + '2,Old Book,Some Author,"Author, Some",,"=""1506711987""","=""""",0,X,P,10,2019,2019,,2026/10/26,,"",to-read,,,,0,0\n')


def test_list_shelves_includes_custom_and_exclusive():
    shelves = {s["name"]: s["count"] for s in list_shelves(CSV)}
    assert shelves == {"2026": 1, "manga": 1, "read": 1, "to-read": 1}


def test_books_on_shelf_cleans_isbns_and_shapes_book():
    [book] = books_on_shelf(CSV, "manga", convertISBNtoISBN13)
    assert book["book_id"] == "1"
    assert book["title"] == "Berserk, Vol. 42 (Berserk, #42)"
    assert book["isbn"] == "" and book["isbn13"] is None
    assert book["user_rating"] == "3.0"


def test_isbn13_derived_from_isbn10():
    [book] = books_on_shelf(CSV, "to-read", convertISBNtoISBN13)
    assert book["isbn"] == "1506711987"
    assert book["isbn13"] == "9781506711980"


def test_rejects_non_goodreads_csv():
    with pytest.raises(GoodreadsCsvError):
        list_shelves("a,b\n1,2\n")


def _row(book_id, title="T", author="A", isbn='=""', isbn13='=""', rating="0", year="2019", orig="2001",
         read="", shelves="", exclusive="read", review=""):
    return (f'{book_id},"{title}",{author},"x",,"{isbn}","{isbn13}",{rating},X,P,10,{year},{orig},{read},'
            f'2026/10/26,"{shelves}","",{exclusive},"{review}",,,1,0\n')


def _isbn(book_csv_isbn, **kw):
    [book] = books_on_shelf(HEADER + _row(1, isbn=book_csv_isbn, **kw), "read", convertISBNtoISBN13)
    return book


def test_bom_is_stripped():
    assert {s["name"] for s in list_shelves("﻿" + CSV)} == {"2026", "manga", "read", "to-read"}


def test_multiline_quoted_review_does_not_break_rows_or_leak():
    review = "line one\nline two, with comma\n\"\"quoted\"\" SECRETREVIEW"
    csv_text = HEADER + _row(1, review=review) + _row(2, exclusive="to-read")
    books = books_on_shelf(csv_text, "read", convertISBNtoISBN13)
    assert [b["book_id"] for b in books] == ["1"]
    assert "SECRETREVIEW" not in str(books)
    assert "SECRETREVIEW" not in str(list_shelves(csv_text))


def test_non_ascii_author():
    [book] = books_on_shelf(HEADER + _row(1, author="Björn Åkesson"), "read", convertISBNtoISBN13)
    assert book["author"] == "Björn Åkesson"


@pytest.mark.parametrize("mangled", ["9.78E+12", '="9.78E+12"', "1.5E+09", "123", "12345678901234"])
def test_mangled_or_malformed_isbn_becomes_empty(mangled):
    book = _isbn(mangled, isbn13=mangled)
    assert book["isbn"] == "" and book["isbn13"] is None


def test_isbn10_with_bad_check_digit_rejected():
    assert _isbn('="1506711988"')["isbn"] == ""


def test_isbn10_with_x_check_digit_kept():
    assert _isbn('="080442957X"')["isbn"] == "080442957X"


def test_valid_isbn13_kept():
    book = _isbn('=""', isbn13='="9781506711980"')
    assert book["isbn13"] == "9781506711980"


def test_duplicate_book_ids_keep_first():
    csv_text = HEADER + _row(7, title="First") + _row(7, title="Second") + _row(8, title="Other")
    books = books_on_shelf(csv_text, "read", convertISBNtoISBN13)
    assert [(b["book_id"], b["title"]) for b in books] == [("7", "First"), ("8", "Other")]


def test_empty_bookshelves_uses_exclusive_shelf_only():
    assert list_shelves(HEADER + _row(1, shelves="", exclusive="read")) == [{"name": "read", "count": 1}]


def test_blank_date_read_passes_through_empty():
    [book] = books_on_shelf(HEADER + _row(1, read=""), "read", convertISBNtoISBN13)
    assert book["user_read_at"] == ""


def test_pubdate_prefers_original_year_falls_back_to_year_published():
    [book] = books_on_shelf(HEADER + _row(1, year="2019", orig="2001"), "read", convertISBNtoISBN13)
    assert book["pubDate"] == "2001"
    [book] = books_on_shelf(HEADER + _row(1, year="2019", orig=""), "read", convertISBNtoISBN13)
    assert book["pubDate"] == "2019"


def test_absent_optional_columns():
    csv_text = ("Book Id,Title,Author,Exclusive Shelf,Bookshelves\n"
                "1,Some Title,Some Author,read,\n")
    [book] = books_on_shelf(csv_text, "read", convertISBNtoISBN13)
    assert book["isbn"] == "" and book["isbn13"] is None
    assert book["pubDate"] == "" and book["user_read_at"] == ""
    assert book["average_rating"] == "" and book["user_rating"] == ""


def test_row_cap_raises_too_large():
    from bookshelf.gr_csv import CsvTooLargeError
    csv_text = HEADER + _row(1) + _row(2) + _row(3)
    with pytest.raises(CsvTooLargeError):
        list_shelves(csv_text, max_rows=2)
    assert len(list_shelves(csv_text, max_rows=3)) == 1
