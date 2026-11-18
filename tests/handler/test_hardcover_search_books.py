import time

import pytest

from bookshelf import hardcover_client as hc
from bookshelf import token_crypto
from tests.fakes import FakeDB, FakeHardcover
from tests.handler.helpers import call, load

OK_BODY = {"data": {"search": {"results": {"hits": [{"document": {
    "id": "55", "title": "Dune", "author_names": ["Frank Herbert"], "release_year": 1965, "isbns": ["0441013597"]}}]}}}}


@pytest.fixture
def setup(monkeypatch):
    fake = FakeHardcover()
    monkeypatch.setattr(hc, "_request", fake)
    db = FakeDB()
    db.add_legacy_user("alice", authtoken="tok")
    db.upsert_hardcover_connection("alice", 1, "a", token_crypto.encrypt("alice", "hc_at"),
                                   token_crypto.encrypt("alice", "hc_rt"), int(time.time()) + 3600,
                                   "read:library read:catalog")
    return db, fake


def _search(db, **over):
    payload = {"username": "alice", "authtoken": "tok", "query": "dune"}
    payload.update(over)
    return call(load("hardcover_search_books"), db, payload)


def test_search_success(setup):
    db, fake = setup
    fake.graphql = [(200, OK_BODY)]
    status, body = _search(db)
    assert status == 200
    assert body == {"results": [{"hardcover_book_id": 55, "title": "Dune", "subtitle": "", "author": "Frank Herbert",
                                 "pubDate": "1965", "isbn": "0441013597", "isbn13": "9780441013593",
                                 "already_uploaded": False}]}


def test_bad_json_body():
    h = load("hardcover_search_books")
    assert h.lambda_handler({"body": "not json"}, {})["statusCode"] == 400


def test_non_object_json_body_is_400(setup):
    h = load("hardcover_search_books")
    for body in ("[]", "5", '"x"', "null"):
        assert h.lambda_handler({"body": body}, {})["statusCode"] == 400


def test_non_string_credentials_are_403(setup):
    db, fake = setup
    for over in ({"username": 5}, {"authtoken": 5}, {"username": ["alice"]}, {"authtoken": {"a": 1}}, {"username": None}):
        assert _search(db, **over)[0] == 403
    assert fake.calls == []


def test_search_marks_already_uploaded(setup):
    db, fake = setup
    db.spines = [{"submitter": "alice", "hardcover_book_id": 55}, {"submitter": "bob", "hardcover_book_id": 56}]
    fake.graphql = [(200, OK_BODY)]
    status, body = _search(db)
    assert status == 200 and body["results"][0]["already_uploaded"] is True


def test_bad_query_is_400(setup):
    db, fake = setup
    for q in (None, "ab", "x" * 201, 7):
        assert _search(db, query=q)[0] == 400
    assert fake.calls == []


def test_bad_session_is_403(setup):
    db, _ = setup
    assert _search(db, authtoken="bad")[0] == 403
    assert call(load("hardcover_search_books"), db, {})[0] == 403


def test_reauth_required_stale_scope_is_401(setup):
    db, fake = setup
    db.connections["alice"]["scopes"] = "read:library"
    status, body = _search(db)
    assert (status, body) == (401, {"error": "hardcover_reauth_required"})
    assert fake.calls == [] and db.connections["alice"]["needs_reauth"] is False


def test_insufficient_scope_is_401(setup):
    db, fake = setup
    fake.graphql = [(403, {"error": "insufficient_scope"})]
    assert _search(db)[0] == 401
    assert db.connections["alice"]["needs_reauth"] is False


def test_rate_limited_is_429(setup):
    db, fake = setup
    fake.graphql = [(429, {})]
    assert _search(db)[0] == 429


def test_hardcover_unreachable_is_502(setup):
    db, fake = setup
    fake.graphql = [(500, {})]
    assert _search(db)[0] == 502
