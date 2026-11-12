#!/usr/bin/env python3
"""Phase 6 (plans/02-hardcover-oauth.md): backfill bookshelf.hardcover_book_id for existing spines.

One-off script, NOT a Lambda, and NOT run as part of any deploy. For every bookshelf row that has a
Goodreads book_id and no hardcover_book_id, look the Goodreads id up in Hardcover's `book_mappings`
(platform id 1 = "goodreads", lowercase) and store the mapped Hardcover book id. Rows with no
mapping stay NULL and keep matching by title and author.

Needs a token with the `read:catalog` scope (book_mappings returns 403 without it). Use a personal
access token or OAuth token from a Hardcover account you control. It is catalog data, not user data.

    export DATABASE_URL=postgresql://...            # local Postgres or prod CockroachDB
    export HARDCOVER_TOKEN=...                      # never commit or paste this anywhere
    uv run python local-dev/scripts/backfill_hardcover_ids.py              # dry run (default)
    uv run python local-dev/scripts/backfill_hardcover_ids.py --apply      # write changes

Prod CockroachDB needs the CA cert: add --sslrootcert /path/to/ca.crt.
Idempotent and resumable: only rows with hardcover_book_id IS NULL are touched, so a re-run picks up
where an interrupted run stopped. Rate limit is 60 requests/min per token; the default pause keeps
under it. One Hardcover book maps to many Goodreads ids (one per edition), so several Goodreads ids
resolving to the same Hardcover id is expected.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

import psycopg2

GRAPHQL_URL = "https://api.hardcover.app/v1/graphql"
GOODREADS_PLATFORM_ID = 1
QUERY = """
query ($platform: Int!, $ids: [String!]!) {
  book_mappings(where: {platform_id: {_eq: $platform}, external_id: {_in: $ids}}, limit: 500) {
    external_id
    book_id
  }
}
"""


def fetch_mappings(token, goodreads_ids):
    """{goodreads_id(str): set(hardcover_book_id)} for one batch. Retries only on HTTP 429."""
    payload = json.dumps({
        "query": QUERY,
        "variables": {"platform": GOODREADS_PLATFORM_ID, "ids": [str(i) for i in goodreads_ids]},
    }).encode("utf-8")
    for attempt in range(5):
        req = urllib.request.Request(
            GRAPHQL_URL, data=payload, method="POST",
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                doc = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                time.sleep(15 * (attempt + 1))
                continue
            sys.exit(f"Hardcover returned HTTP {e.code} (403 means the token lacks read:catalog)")
        if doc.get("errors"):
            sys.exit("GraphQL error: " + str(doc["errors"][0].get("message")))
        result = {}
        for row in doc["data"]["book_mappings"]:
            result.setdefault(str(row["external_id"]), set()).add(int(row["book_id"]))
        return result
    sys.exit("gave up after repeated rate limiting")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write changes (default is a dry run)")
    ap.add_argument("--batch", type=int, default=100, help="Goodreads ids per request (rows cap is 500)")
    ap.add_argument("--pause", type=float, default=1.2, help="seconds between requests (limit: 60/min)")
    ap.add_argument("--sslrootcert", help="CA cert path for CockroachDB")
    args = ap.parse_args()

    token = os.environ.get("HARDCOVER_TOKEN")
    db_url = os.environ.get("DATABASE_URL")
    if not token or not db_url:
        sys.exit("set HARDCOVER_TOKEN and DATABASE_URL in the environment")

    conn = psycopg2.connect(db_url, sslrootcert=args.sslrootcert) if args.sslrootcert else psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT book_id FROM bookshelf WHERE book_id IS NOT NULL AND hardcover_book_id IS NULL ORDER BY book_id")
        goodreads_ids = [r[0] for r in cur.fetchall()]
    conn.commit()
    print(f"{len(goodreads_ids)} distinct Goodreads ids to resolve ({'APPLY' if args.apply else 'dry run'})")

    mapped = ambiguous = unmapped = updated_rows = 0
    for start in range(0, len(goodreads_ids), args.batch):
        batch = goodreads_ids[start:start + args.batch]
        mappings = fetch_mappings(token, batch)
        with conn.cursor() as cur:
            for gid in batch:
                hc_ids = mappings.get(str(gid), set())
                if not hc_ids:
                    unmapped += 1
                elif len(hc_ids) > 1:
                    ambiguous += 1  # conflicting mappings: leave NULL, title+author matching still works
                    print(f"skip Goodreads {gid}: maps to several Hardcover books {sorted(hc_ids)}")
                else:
                    mapped += 1
                    if args.apply:
                        cur.execute(
                            "UPDATE bookshelf SET hardcover_book_id = %s WHERE book_id = %s AND hardcover_book_id IS NULL",
                            (next(iter(hc_ids)), gid))
                        updated_rows += cur.rowcount
        conn.commit()
        print(f"batch {start}-{start + len(batch)} done (mapped={mapped} ambiguous={ambiguous} unmapped={unmapped})")
        time.sleep(args.pause)

    print(f"finished: mapped={mapped} ambiguous={ambiguous} unmapped={unmapped} rows_updated={updated_rows}")
    if not args.apply:
        print("dry run: nothing was written; re-run with --apply")


if __name__ == "__main__":
    main()
