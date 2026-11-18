import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_template_no_longer_references_goodreads_scraper():
    template = (ROOT / "infra" / "template.yaml").read_text()
    for needle in ("get_gr_book_details", "getgrbookdetails", "GetGRBookDetails"):
        assert needle.lower() not in template.lower()


def test_deprecation_note_exists():
    assert (ROOT / "lambdas" / "get_gr_book_details" / "DEPRECATED.md").is_file()


def test_nothing_imports_from_the_deprecated_folder():
    pattern = re.compile(r"get_gr_book_details")
    offenders = []
    for base in ("src", "lambdas", "tests"):
        for path in (ROOT / base).rglob("*.py"):
            if "get_gr_book_details" in path.parts or path.name == pathlib.Path(__file__).name:
                continue
            if pattern.search(path.read_text()):
                offenders.append(str(path))
    assert offenders == []


NEEDLES = ("get_gr_book_details", "getgrbookdetails")


def test_no_source_or_lambda_references_the_scraper():
    offenders = []
    for base in ("lambdas", "src"):
        for path in (ROOT / base).rglob("*.py"):
            if "get_gr_book_details" in path.parts or path.resolve() == pathlib.Path(__file__).resolve():
                continue
            text = path.read_text().lower()
            if any(n in text for n in NEEDLES):
                offenders.append(str(path))
    assert offenders == []
