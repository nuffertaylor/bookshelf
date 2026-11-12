import json

import pytest

from bookshelf import hardcover_client as hc
from bookshelf import token_crypto
from tests.fakes import FakeDB, FakeHardcover
from tests.handler.helpers import call, load


def _user_book(book_id, title, author):
    return {"rating": 4.0, "last_read_date": "2024-02-02", "book_id": book_id,
            "edition": {"isbn_10": None, "isbn_13": "9781111111111"},
            "book": {"id": book_id, "title": title, "release_year": 2001,
                     "contributions": [{"contribution": "Author", "author": {"name": author}}]}}


@pytest.fixture
def setup(monkeypatch):
    import time
    fake = FakeHardcover()
    monkeypatch.setattr(hc, "_request", fake)
    db = FakeDB()
    db.add_legacy_user("alice", authtoken="tok")
    db.upsert_hardcover_connection("alice", 1, "a", token_crypto.encrypt("alice", "hc_at"),
                                   token_crypto.encrypt("alice", "hc_rt"), int(time.time()) + 3600, "s")
    return db, fake


def test_shelves_requires_session(setup):
    db, _ = setup
    assert call(load("get_hardcover_shelves"), db, {"username": "alice", "authtoken": "bad"})[0] == 403
    assert call(load("get_hardcover_shelves"), db, {})[0] == 403


def test_shelves_ok(setup):
    db, fake = setup
    me = {"id": 1, "lists": [{"id": 5, "name": "Favs", "books_count": 2}]}
    for sid in range(1, 6):
        me[f"s{sid}"] = {"aggregate": {"count": 1}}
    fake.graphql = [(200, {"data": {"me": [me]}})]
    status, body = call(load("get_hardcover_shelves"), db, {"username": "alice", "authtoken": "tok"})
    assert status == 200 and body["shelves"][-1] == {"id": "list:5", "name": "Favs", "count": 2}
    assert fake.calls_to("/v1/graphql")[0]["headers"]["Authorization"] == "Bearer hc_at"


def test_shelf_returns_found_and_unfound_with_hardcover_ids(setup):
    db, fake = setup
    db.spines = [{"upload_id": "u1", "title": "Known", "author": "Ann", "book_id": None,
                  "hardcover_book_id": 10, "fileName": "k.jpg"}]
    fake.graphql = [(200, {"data": {"me": [{"user_books": [_user_book(10, "Known", "Ann"), _user_book(11, "New", "Bo")]}]}})]
    status, body = call(load("get_hardcover_shelf"), db, {"username": "alice", "authtoken": "tok", "shelf": "status:3"})
    assert status == 200
    assert [s["fileName"] for s in body["found"][0]] == ["k.jpg"]
    assert [b["hardcover_book_id"] for b in body["unfound"]] == [11]
    assert "book_id" not in body["unfound"][0]
    assert json.loads(fake.calls_to("/v1/graphql")[0]["data"])["variables"]["status"] == 3


def test_shelf_validation(setup):
    db, _ = setup
    h = load("get_hardcover_shelf")
    assert call(h, db, {"username": "alice", "authtoken": "tok"})[0] == 400
    assert call(h, db, {"username": "alice", "authtoken": "tok", "shelf": "status:99"})[0] == 404


def test_reauth_required_is_401_and_session_survives(setup):
    db, fake = setup
    fake.graphql = [(401, {})]
    status, body = call(load("get_hardcover_shelf"), db, {"username": "alice", "authtoken": "tok", "shelf": "status:3"})
    assert status == 401 and body == {"error": "hardcover_reauth_required"}
    assert db.connections["alice"]["needs_reauth"] is True
    assert db.validate_username_authtoken("alice", "tok")
    # and it stays 401 without touching Hardcover again
    fake.calls.clear()
    assert call(load("get_hardcover_shelves"), db, {"username": "alice", "authtoken": "tok"})[0] == 401
    assert fake.calls == []


def test_unlinked_account_is_reauth_required(setup):
    db, _ = setup
    db.add_legacy_user("bob", authtoken="t2")
    status, body = call(load("get_hardcover_shelves"), db, {"username": "bob", "authtoken": "t2"})
    assert status == 401 and body["error"] == "hardcover_reauth_required"


def test_rate_limit_is_429(setup):
    db, fake = setup
    fake.graphql = [(429, {})]
    status, _ = call(load("get_hardcover_shelf"), db, {"username": "alice", "authtoken": "tok", "shelf": "status:3"})
    assert status == 429


def test_upstream_failure_is_502(setup):
    db, fake = setup
    fake.graphql = [(500, {})]
    assert call(load("get_hardcover_shelves"), db, {"username": "alice", "authtoken": "tok"})[0] == 502
