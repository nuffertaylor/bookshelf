import pytest

from bookshelf.text_match import match_key, normalize_author, normalize_title


@pytest.mark.parametrize("stored, requested", [
    # Goodreads stores the series in the title; Hardcover does not.
    ("Words of Radiance (The Stormlight Archive, #2)", "Words of Radiance"),
    ("The Unspoken Name (The Serpent Gates, #1)", "The Unspoken Name"),
    ("One Piece, Vol. 17: Hiriluk's Cherry Blossoms (One Piece, #17)", "One Piece, Vol. 17: Hiriluk’s Cherry Blossoms"),
    # case, edge spaces and repeated spaces
    ("  DUNE ", "dune"),
    ("The  Alloy   of Law", "The Alloy of Law"),
    # curly vs straight quotes
    ("The Book That Wouldn't Burn", "The Book That Wouldn’t Burn"),
    ('The "Real" Story', "The “Real” Story"),
    # series suffix with other numbering styles
    ("Dune (Dune Chronicles, #1)", "Dune"),
    ("Foundation (Foundation #1)", "Foundation"),
])
def test_titles_that_are_the_same_book_normalize_equal(stored, requested):
    assert normalize_title(stored) == normalize_title(requested)


@pytest.mark.parametrize("a, b", [
    ("Foundation (Foundation, #1)", "Foundation and Empire"),
    ("Dune", "Dune Messiah"),
    ("Dune", "Dune Messiah (Dune, #2)"),
    ("The Hunter", "The Hunted"),
])
def test_different_books_do_not_normalize_equal(a, b):
    assert normalize_title(a) != normalize_title(b)


def test_only_a_trailing_series_suffix_is_removed():
    # a parenthetical in the middle, or without a "#n", is part of the title
    assert normalize_title("Dune (Deluxe Edition)") == "dune (deluxe edition)"
    assert normalize_title("The (Not So) Great Escape") == "the (not so) great escape"
    assert normalize_title("Ulysses (Annotated, 1922)") == "ulysses (annotated, 1922)"


def test_a_title_that_is_only_a_series_suffix_is_kept_not_emptied():
    assert normalize_title("(Series, #1)") == "(series, #1)"


def test_none_and_empty_are_empty():
    assert normalize_title(None) == "" and normalize_title("") == ""
    assert normalize_author(None) == "" and normalize_author("  ") == ""


def test_author_spacing_and_case():
    assert normalize_author("Drew  Hayes") == normalize_author("drew hayes ")
    assert normalize_author("N. K. Jemisin") != normalize_author("N.K. Jemisin")  # initials are not guessed at


def test_non_ascii_survives():
    assert normalize_title("Solaris (Solaris, #1)") == "solaris"
    assert normalize_author("Stanisław Lem") == "stanisław lem"
    assert normalize_author("Stanisław Lem") != normalize_author("Stanislaw Lem")


def test_match_key_requires_title_and_author_to_be_present():
    assert match_key("Dune", "Frank Herbert") == ("dune", "frank herbert")
