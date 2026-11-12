# Plan 1: Goodreads CSV Export Import (hardening what already exists)

**Status:** Revised after merging `refactor` into `BRIO-35596`
**Scope:** Backend only. No frontend work.

## 1. Where things stand

Goodreads removed its RSS feed, which broke `lambdas/get_gr_bookshelf`. The `refactor` branch (commit `b31ddd8`, "added importGRLibraryCsv function") already contains a working replacement, now on this branch:

| Piece | Location |
|---|---|
| Handler | `lambdas/import_gr_library_csv/handler.py` |
| Parser | `src/bookshelf/gr_csv.py` (`list_shelves`, `books_on_shelf`, `GoodreadsCsvError`) |
| Route | `POST /importgrlibrary` (`importGRLibraryCsv` in `infra/template.yaml`) |
| Parser tests | `tests/unit/test_gr_csv.py` (4 tests) |
| Shared matcher | `which_books_found(db, books)` and `convertISBNtoISBN13` in `src/bookshelf/bookshelf.py` |
| HTTP helpers | `parse_event`, `http_result` in `src/bookshelf/http.py` |

**Existing contract (keep it; the frontend may already depend on it):**

- Request body `{"csv": "<file text>"}` returns `{"shelves": [{"name", "count"}]}`, largest first.
- Request body `{"csv": "...", "shelf": "<name>"}` returns `{"found": [[...]], "unfound": [...]}`, the same shape the RSS lambda returned.
- Responses go through `http_result`, which sets the real HTTP status and also wraps `{"statusCode", "body"}` inside the JSON body. Errors use `{"error": "message"}` as the body.

This plan therefore no longer designs a new lambda. It lists the gaps between what exists and what we decided, plus bugs found when reading the code against the real export.

## 2. Decisions already made

| Decision | Choice |
|---|---|
| Transport | Direct POST of the CSV text, parsed in memory. Nothing is stored. |
| Oversized files | Reject with 413 and leave a `TODO` for S3 or another path. Real exports are far below the limit. |
| Auth | None, as with the RSS endpoint it replaces. |

## 3. What the real export looks like (sample: 953,763 bytes, 1,453 rows, 23 columns)

Findings, with whether the existing code already handles them:

| Finding | Handled today? |
|---|---|
| UTF-8 BOM at file start | Yes (`lstrip("﻿")`) |
| ISBNs wrapped as `="1506711987"`; `=""` when empty (264 rows lack ISBN, 236 lack ISBN13) | Yes, via `_clean_isbn` (but see bug B1) |
| Shelf membership is `Exclusive Shelf` plus the comma-separated custom `Bookshelves` (`read` is not listed in `Bookshelves`) | Yes (`_shelves_of`) |
| Titles carry series suffixes in 477 of 1,453 rows, e.g. `(The Serpent Gates, #1)` | **No** (§4.4) |
| `Book Id` is the Goodreads ID, equal to `bookshelf.book_id` | Yes (used as `book_id`) |
| No `Average Rating` column in this export (older exports have one) | Yes (`row.get`, empty string) |
| Review and note text, and cells containing newlines | Parser only copies a fixed set of fields, so reviews and notes never reach the response |
| 53 `read` rows have no `Date Read`; dates are `YYYY/MM/DD` | Passed through as-is |
| Non-ASCII authors | Yes (text mode) |
| Private data in the file | Safe as long as nothing logs rows (§4.8) |

## 4. Gaps to close

### 4.1 Size limit (decided, not yet implemented)

Lambda's synchronous payload limit is 6 MB and API Gateway's is 10 MB. The sample is about 1 MB.

- In the handler, before any parsing: if `len(csv_text) > MAX_CSV_CHARS` (propose `4_000_000`), return `http_result(413, {"error": "CSV is larger than 4 MB. Large-file support is not available yet."})`.
- Also cap parsed rows at `MAX_ROWS = 20_000` and return 413 beyond it.
- Leave this at the check:
  ```python
  # TODO: files over MAX_CSV_CHARS are rejected. If real users hit this, add an S3 presigned-upload
  # path (client PUTs to S3, Lambda reads from S3, lifecycle rule deletes after a day), or some
  # other solution. Stored exports contain private reviews and notes, so that needs a privacy review.
  ```

### 4.2 Malformed requests return 500

`parse_event` calls `json.loads` on `body`. A non-JSON body raises, and API Gateway returns a bare 500. Catch `ValueError` in the handler and return `http_result(400, {"error": "request body must be JSON"})`. Also reject a non-string `csv` with 400, and a non-UTF-8 body if it surfaces.

### 4.3 Unknown shelf is indistinguishable from an empty shelf

`books_on_shelf` returns `[]` for a shelf that doesn't exist, and the handler answers 200 with empty `found` and `unfound`. Decide (Q1) whether to return 404 `{"error": "shelf 'x' not found"}`. A typo and an empty library currently look the same.

### 4.4 Series suffix in titles can break the title fallback

`get_spines_batch_by_title_author` compares `LOWER(TRIM(title))` for equality, and the CSV title keeps the suffix (`The Unspoken Name (The Serpent Gates, #1)`). The ID match (`book_id`) still catches most books, so the fallback only matters when a spine was uploaded for a different edition of the same book.

- **Verify first:** on the dev DB (seed data is in `local-dev/seed/bookshelf_data.json`) and, if possible, prod, look at whether stored spine titles include the suffix. The RSS `<title>` historically did, which would make exact comparison correct.
- If stored titles have no suffix, add a stripped variant to the match: `re.sub(r'\s*\([^()]*#\s*\d+[^()]*\)\s*$', '', title)`. Put the stripped title in the query as an extra candidate. Never change the title returned to the frontend.

### 4.5 Bugs in `gr_csv.py` (found by reading against the real export)

- **B1: Excel-mangled ISBNs become garbage.** `_clean_isbn` deletes every character that isn't a digit or `X`, so a spreadsheet-saved value like `9.78E+12` becomes `97812`. Fix: after cleaning, accept only 10 or 13 characters (and for ISBN-10 check the check digit); otherwise return `""`. Then `convertISBNtoISBN13("")` correctly returns `None`.
- **B2: Duplicate `Book Id`s are not removed.** None in the sample, but a hand-edited CSV could produce them. De-duplicate in `books_on_shelf`, keeping the first.
- **B3: `pubDate` source.** The importer uses `Year Published` (this edition's year). The RSS value was `book_published`. Check which one the frontend and spine records expect (compare `bookshelf.pubDate` values in seed data), then switch to `Original Publication Year` if appropriate, falling back to `Year Published`.
- **B4: `user_read_at` and `user_rating` are passed through raw** (`2026/10/26`, `"3.0"`). The RSS values had other formats. Confirm in the frontend (`Create.tsx`, `getgrbookshelfResponse`) that sorting or display copes with these. Normalising is optional.

### 4.6 Matching performance on big shelves

`which_books_found` sends one query with an `OR (title AND author)` clause per book plus an `IN (…)` list of IDs. For the 741-book `read` shelf that is roughly 1,500 parameters in one statement.

- Measure it against the seeded local DB with a synthetic 750-book shelf. If it is slower than a couple of seconds, chunk the book list (about 200 per query) inside `which_books_found` and concatenate the results.
- Check with `EXPLAIN` whether `LOWER(TRIM(title))` matching does a sequential scan. If it does and the table is large, add a functional index. That is an optional follow-up.

### 4.7 Memory and timeout

The function inherits `Timeout: 30` and the default 128 MB. Parsing a 1 MB file is trivial, but the response with 741 books and several spine options each can be large. Set `MemorySize: 512` on `ImportGRLibraryCsvFunction` in `infra/template.yaml` and keep an eye on response size against the 6 MB response limit (the shelf-at-a-time design is what keeps this safe).

### 4.8 Logging and privacy

The handler logs only counts (`"looking for N books"`), which is fine. Add a rule to keep it that way: never log row contents. Add a test (§5) asserting that `My Review`, `Private Notes` and `Spoiler` text never appears in a response.

### 4.9 Tests

`tests/unit/test_gr_csv.py` covers the parser basics. Missing:

- Handler tests under `tests/handler/` following `test_login_register.py` (patch `psycopg2.connect`, patch `_get_db`): 413 on oversized text, 400 on non-JSON body, 400 on a non-Goodreads CSV, shelf listing, `found`/`unfound` shape, unknown shelf behaviour (once decided).
- Parser tests for: BOM, quoted multi-line review cell, non-ASCII author, `9.78E+12` ISBN (B1), duplicate IDs (B2), empty `Bookshelves`, blank `Date Read`, absent optional columns, a review-text-never-leaks assertion.
- Do **not** commit the real export. Hand-craft a fixture of about 12 rows, or build rows inline like the existing test does.

### 4.10 Retire the dead RSS lambda

`lambdas/get_gr_bookshelf/handler.py` still calls `feedparser`; Goodreads returns no entries now, so it silently reports zero books.

1. Replace its body with `http_result(410, {"error": "Goodreads RSS is no longer available. Upload your Goodreads export instead."})`, so the frontend can show a real message.
2. Once nothing needs it, remove `import feedparser` from `src/bookshelf/bookshelf.py` (line 7, unused there), then `feedparser` from `local-dev/layer-requirements.txt` and `pyproject.toml`. That shrinks the layer.
3. The `get_books_from_shelf` function and its route can be deleted at the next cleanup.

## 5. Implementation order

1. Parser fixes B1/B2 (and B3/B4 after checking the frontend) with tests.
2. Handler hardening: size limit, row cap, 400s, unknown shelf, with handler tests.
3. Title-suffix verification (§4.4), then the matching tweak if needed.
4. Performance measurement (§4.6) and `MemorySize` (§4.7).
5. 410 for the RSS lambda, then dependency cleanup.

Run `make test` and `make lint` at each step. The local stack is `make dev` then `make local` (SAM on port 3001), and the harness events live in `tests/` and `local-dev/`.

## 6. Open questions

- **Q1. RESOLVED:** an unknown shelf returns 404 `{"error": "shelf '<name>' not found in this export"}` (implemented).
- **Q2.** Do you want base64 input support (`csv_base64`)? It would guard against any mangling of the BOM or newlines in transit. I've left it out since the existing contract is plain text and works for UTF-8.
- **Q3. RESOLVED:** `pubDate` uses `Original Publication Year`, falling back to `Year Published` (implemented; matches the seed data).
- **Blank `Date Read`: RESOLVED:** left as an empty string, no normalisation.
- **Q4.** Do you want a whole-library mode (no shelf, all books)? It would likely exceed the 6 MB response limit, so I'd say no.

## 7. Out of scope

Server-side storage of exports and the S3 upload path (the `TODO`), other platforms (StoryGraph, LibraryThing), and anything in the frontend.
