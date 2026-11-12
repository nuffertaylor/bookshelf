"""Two simultaneous refreshes must spend the refresh token exactly once.

Needs a real Postgres (the row lock is the thing under test). Set TEST_DATABASE_URL, or the
docker-compose default postgresql://postgres:dev@localhost:5432/bookshelf is tried. If nothing is
reachable the test is skipped. The schema is loaded from local-dev/migrate.sql into a throwaway
schema that is dropped afterwards, so a bare CI Postgres works and no real data is touched.
"""
import json
import os
import pathlib
import threading
import time
import uuid

import pytest

import psycopg2
from bookshelf import hardcover_client as hc
from bookshelf import token_crypto
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from tests.fakes import token_response

DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:dev@localhost:5432/bookshelf")
MIGRATE_SQL = pathlib.Path(__file__).resolve().parents[2] / "local-dev" / "migrate.sql"


def _connect(schema):
    return psycopg2.connect(DB_URL, options=f"-c search_path={schema}", connect_timeout=3)


def _make_dao(schema):
    dao = CockroachDAO.__new__(CockroachDAO)  # skip __init__ (it would connect without our search_path)
    dao.conn = _connect(schema)
    return dao


@pytest.fixture
def schema():
    name = "t_" + uuid.uuid4().hex[:12]
    try:
        admin = psycopg2.connect(DB_URL, connect_timeout=3)
    except psycopg2.OperationalError:
        pytest.skip("no local Postgres reachable (set TEST_DATABASE_URL)")
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f"CREATE SCHEMA {name}")
    try:
        conn = _connect(name)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(MIGRATE_SQL.read_text())
        conn.close()
        yield name
    finally:
        with admin.cursor() as cur:
            cur.execute(f"DROP SCHEMA {name} CASCADE")
        admin.close()


def test_two_simultaneous_refreshes_spend_the_refresh_token_once(schema, monkeypatch):
    setup = _make_dao(schema)
    setup.exec_statement(
        "INSERT INTO bookshelf_users (username, authtoken, expiry, banned) VALUES ('alice', 't', 9999999999, false)")
    setup.upsert_hardcover_connection(
        "alice", 42, "alice_hc", token_crypto.encrypt("alice", "hc_at_old"),
        token_crypto.encrypt("alice", "hc_rt_old"), int(time.time()) - 5, "read:library")

    spent = []
    lock = threading.Lock()

    def fake_request(url, data=None, headers=None, method="POST", timeout=15):
        assert url.endswith("/oauth2/token")
        form = data.decode()
        with lock:
            spent.append(form)
        time.sleep(0.4)  # long enough that the second caller reaches the row lock meanwhile
        if "hc_rt_old" not in form:
            return 400, {}, json.dumps({"error": "invalid_grant"})  # a replay: Hardcover would revoke everything
        return 200, {}, json.dumps(token_response(access="hc_at_new", refresh="hc_rt_new"))

    monkeypatch.setattr(hc, "_request", fake_request)

    results = []
    errors = []

    def worker():
        dao = _make_dao(schema)
        try:
            results.append(hc.get_valid_access_token(dao, "alice"))
        except Exception as e:  # noqa: BLE001
            errors.append(e)
        finally:
            dao.conn.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    assert errors == []
    assert results == ["hc_at_new", "hc_at_new"]
    assert len(spent) == 1, "the refresh token was spent more than once"
    conn = setup.get_hardcover_connection("alice")
    assert token_crypto.decrypt("alice", conn["refresh_token_enc"]) == "hc_rt_new"
    assert conn["needs_reauth"] is False
    setup.conn.close()
