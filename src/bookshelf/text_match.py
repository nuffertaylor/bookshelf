"""How titles and authors are compared when matching a book to stored spines.

Goodreads puts the series in the title ("Words of Radiance (The Stormlight Archive, #2)"); Hardcover does
not ("Words of Radiance"). Quote style and spacing also differ between the two. Both sides are reduced to
the same key before comparing, so those differences don't make a book look missing.

This only affects comparison. Titles shown to the user and stored in the database are never changed.
Keep it one function in one place: the lookup (`CockroachDAO.get_spines_batch_by_title_author`) and the
grouping (`which_books_found`) must agree, so neither re-implements these rules.
"""
import re

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_SPACES = re.compile(r"\s+")
# A trailing "(Series Name, #3)" (or "#3" with other punctuation). Only a final parenthetical that contains
# "#<digits>" counts, so "(Deluxe Edition)" or "(Annotated, 1922)" are part of the title and stay.
_SERIES_SUFFIX = re.compile(r"\s*\([^()]*#\s*\d+[^()]*\)\s*$")


def _clean(text):
    return _SPACES.sub(" ", text).strip().lower()


def normalize_title(title):
    base = (title or "").translate(_QUOTES)
    # A title that is nothing but a suffix keeps it rather than becoming empty (and matching every other empty).
    return _clean(_SERIES_SUFFIX.sub("", base)) or _clean(base)


def normalize_author(author):
    return _clean((author or "").translate(_QUOTES))


def match_key(title, author):
    """What two books must share to count as the same by title and author."""
    return normalize_title(title), normalize_author(author)
