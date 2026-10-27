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
