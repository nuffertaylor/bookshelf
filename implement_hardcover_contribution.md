# Plan: Contribute spines through Hardcover search (backend)

**Status:** Draft for review (2026-11-18). Companion plan: `bookshelf-ts-site/implement_hardcover_contribution.md` (frontend).
**Scope:** Python Lambdas, DAO, SAM template, tests. Replaces the Goodreads URL/ID contribute flow (`get_gr_book_details`, which scrapes goodreads.com) with a Hardcover catalog search.
**Sources:** `~/projects/hardcover-docs` (`api/guides/Searching.mdx`, `api/GraphQL/Actions.mdx`, `api/OAuth.mdx`), `plans/02-hardcover-oauth.md`, search spike run 2026-11-18.

## 1. Goal

A signed-in user with a linked Hardcover account types into one search box and gets a list of matching books from Hardcover's **public catalog** (not just their own library). Picking one opens the existing spine upload prefilled with that book's data and `hardcover_book_id`. `upload_spine` already accepts a `hardcover_book_id` with no Goodreads `book_id`, so the upload path needs no change.

## 2. Decisions

| Decision | Choice |
|---|---|
| Whose token runs the search | The signed-in user's own Hardcover OAuth token. Rate limits are per Hardcover user (60/min, burst 10, 5,000/day), so each user has their own budget and the app's own API key and free tier are never involved. |
| Who may contribute | Only a user with a linked, valid Hardcover connection. No manual-entry fallback. |
| Search box | One box. The frontend debounces (500 ms) and sends the text as `query`. Users add detail in the same box to narrow results. |
| Results | Title, author, year, plus the data needed to prefill Upload. No cover images. Fewer than 15 results per search. |
| Goodreads scraper | Keep the code, mark it deprecated, remove it from the build and deploy, and delete the deployed lambda. |
| Existing users missing the new scope | Prompted to reconnect **only when they open Contribute**. Shelf loading keeps working for them. |

## 3. What the spike established (2026-11-18)

- `search(query:, query_type: "Book", per_page:, page:)` returns `results` as Typesense JSON: `hits[].document` plus `found`. One search costs 1 request.
- A hit's `document` has `id` (**a string**), `title`, `subtitle`, `author_names` (list), `contributions` (same shape `author_name()` already handles: `author.name`, `contribution`), `release_year`, `isbns` (a mixed list of ISBN-10 and ISBN-13), `slug`, `pages`, `compilation`, `users_count`.
- Search is global, not limited to the user's library.
- Ranking is fuzzy and noisy. "project hail mary" returns the real book first, then study guides and box sets. Adding the author ("hail mary andy weir") ranked the study guides above the real book. See Phase 2.
- **Scope is not fully settled.** The docs say `search` needs `read:catalog` (or `read:catalog:search`). The spike token had `read:catalog` and `read:library` (among others), so it never tested `read:library` alone. `USER_SCOPE` today is `read:me:email read:library read:lists openid`. Phase 1 settles this with a real OAuth token.
- Python 3.14 rejected a CA certificate on the developer's network (`CA cert does not include key usage extension`). Check which Python the backend uses locally and in the Lambda runtime (Phase 1), so this doesn't break the local OAuth check.

## 4. Phase 1: Confirm the scope with a real OAuth token (gate)

1. Locally, with the current `USER_SCOPE`, sign in with Hardcover through the existing flow and run a `search` GraphQL call with that token.
   - **403 `insufficient_scope`** (expected): continue to step 2.
   - **Success**: skip the scope change. Keep steps 3 and 4, which still guard against stale connections.
2. Add `read:catalog` to `USER_SCOPE` (`src/bookshelf/hardcover_client.py`). It's already in the registered scope ceiling, so no app changes are needed. Do **not** use `read:catalog:search`, because it isn't in the ceiling. Sign in again and confirm the search works.
3. Update `tests/unit/test_hardcover_client.py` and the `hardcover_auth_start` tests, which assert the scope string.
4. Check the Python version the backend runs under (`pyproject.toml`, the Lambda runtime in `infra/template.yaml`, and the local `.venv`). Make sure outbound HTTPS to `api.hardcover.app` works in the local environment.

**Gate:** if the search still fails with `read:catalog`, stop and reassess before building anything else.

## 5. Phase 2: Search and normalization (`src/bookshelf/hardcover_library.py`)

Add `search_books(db, username, query)`:

- Validate `query`: a string, trimmed, 3 to 200 characters. Otherwise raise `ValueError`, which the handler maps to 400.
- Call `user_graphql(db, username, SEARCH_QUERY, {"q": query, "n": 10}, required_scope="read:catalog")`. The query is parameterized, so there's no string interpolation.
- `results` can arrive as a dict or a JSON string, so handle both. Missing or odd shapes return an empty list and never crash.
- Normalize each hit to:
  ```
  {hardcover_book_id: int(id), title, subtitle, author, pubDate: str(release_year) or "", isbn, isbn13, already_uploaded: bool}
  ```
  - `author`: reuse `author_name()` on `contributions`, falling back to `author_names[0]`.
  - ISBNs: pick by length (10 digits or 13 digits, allowing a trailing `X`). Compute ISBN-13 from ISBN-10 with the existing `convertISBNtoISBN13` when only a 10 is present.
  - Skip hits whose `id` isn't an integer.
- Do not return, log or store the raw hit, images, or descriptions. Do not store search results.
- **Ranking tuning (time-boxed):** try `fields`/`weights` (for example a higher `author_names` weight) against the three spike queries, plus "project hail mary andy weir" and a few of the user's own titles. Keep Typesense's default ordering unless a change is clearly better. Record the result in this plan.

## 6. Phase 3: Scope checks and error mapping (`hardcover_client.py`)

- Add an optional `required_scope` argument to `user_graphql`. Before the network call, check the stored connection's `scopes` string. If `required_scope` is missing, raise `HardcoverReauthRequired` right away. This avoids a wasted Hardcover request for connections made before the scope was added.
- Map a Hardcover `403` with `error == "insufficient_scope"` to `HardcoverReauthRequired` as well. The existing `error_response` already turns that into `401 {"error": "hardcover_reauth_required"}`, which the frontend treats as "reconnect Hardcover".
- **Do not** call `mark_hardcover_needs_reauth` for these two cases. The connection is still valid for shelf loading, and marking it would block that.
- After a reconnect, `hardcover_auth_callback` already saves the new `tokens["scope"]` (`handler.py:85`), so the connection upgrades itself.
- No server-side retries on 429. Pass `429` through, as `error_response` does now.

## 7. Phase 4: "Already uploaded" flag (DAO)

- Add a DAO method such as `get_uploaded_hardcover_ids(username, ids)`: one query, `SELECT hardcover_book_id FROM bookshelf WHERE submitter = %s AND hardcover_book_id IN (...)`. Use it in `search_books` to set `already_uploaded`. Never run one query per hit.
- Relies on the Phase 6 backfill having populated `hardcover_book_id` on spines uploaded through Goodreads. Without that, old Goodreads uploads won't be flagged, and `upload_spine`'s own check still catches duplicates when the user submits.
- Add the method to the fake DAO in `tests/fakes.py`.

## 8. Phase 5: Lambda and route

- New `lambdas/hardcover_search_books/handler.py`, modeled on `get_hardcover_shelves`: `POST /hardcover/search` with `{"username", "authtoken", "query"}`, returning `{"results": [...]}`. Status codes: 400 bad body or query, 403 invalid session, 401 `hardcover_reauth_required`, 429 rate limited, 502 Hardcover unreachable.
- Add `HardcoverSearchBooksFunction` to `infra/template.yaml`, copying `GetHardcoverShelvesFunction` (same policies, env vars, 30 to 60 s timeout).

## 9. Phase 6: Deprecate the Goodreads scraper

- Keep `lambdas/get_gr_book_details/` on disk. Add a short `DEPRECATED.md` in that folder (why, and that it's no longer built or deployed).
- Remove `GetGRBookDetailsFunction` and its `/getgrbookdetails` route from `infra/template.yaml`. Deploying the stack deletes the deployed lambda and the API route.
- Update `docs/TODO-setup-aws-deploy.md`, which has a line about upgrading its `nodejs20.x` runtime. That item no longer applies.
- Keep `set_goodreads_id`, `get_gr_bookshelf` and the CSV import. They belong to the shelf-import feature.

## 10. Testing

**Rule:** every phase ships with its own tests, and a phase isn't done until its tests and the full existing suite pass. Run `uv run pytest` (with the local Postgres from `make dev` up, so the real-database tests don't skip) at the end of each phase. Don't start the next phase on a red suite.

### 10.1 Tests written inside each phase

| Phase | Tests |
|---|---|
| 1 (scope) | Update the tests that assert the scope string (`tests/unit/test_hardcover_client.py`, `tests/handler/test_hardcover_auth_start.py`) so they expect the final `USER_SCOPE`. |
| 2 (search) | Unit tests in `tests/unit/test_hardcover_library.py`: hit normalization (ISBN-10/13 picking, missing author, subtitle, non-integer id skipped, `results` as a dict and as a JSON string, empty and malformed results), and query validation (too short, too long, not a string). |
| 3 (scope checks) | Unit tests in `tests/unit/test_hardcover_client.py`: a stale connection (no `read:catalog` in `scopes`) raises `HardcoverReauthRequired` **without** a network call, `403 insufficient_scope` maps to the same, neither case calls `mark_hardcover_needs_reauth`, and shelf loading still works for that connection. |
| 4 (already uploaded) | DAO test against the local Postgres (pattern in `tests/unit/test_dao_hardcover.py`): returns only the user's own uploads, handles an empty id list, and uses a single query. Add the method to `tests/fakes.py`. |
| 5 (lambda) | Handler tests (pattern in `tests/handler/test_hardcover_library_handlers.py`, patching `_request`): success, bad JSON body, bad query, bad session (403), reauth required (401), 429, 502. |
| 6 (deprecation) | A check that `infra/template.yaml` no longer references `get_gr_book_details` or `/getgrbookdetails` (a simple test or grep in CI), and that no other lambda or module imports from that folder. |

All new automated tests patch `hardcover_client._request`. Nothing in the suite calls the real Hardcover API or needs a token.

### 10.2 Phase 7: Integration and regression testing

Run after Phases 1 to 6 are done, before merging.

1. **Local end-to-end with the frontend.** Run the backend locally (the same way `plans/04-hardcover-manual-steps.md` Part B does) and the frontend from `bookshelf-ts-site` pointed at it. Using a real Hardcover account, do the whole flow: sign in, Contribute, type a title, pick a result, upload a spine, then confirm the row in the local database has the right `hardcover_book_id` and `submitter` and that the spine appears on a generated shelf.
2. **Contract check.** Compare a real `POST /hardcover/search` response with the frontend plan section 3 (field names and types, `hardcover_book_id` as a number). Fix whichever side is wrong.
3. **Stale-scope scenario.** With a connection created before the scope change (or one edited in the local database to drop `read:catalog` from `scopes`), confirm Contribute shows the reconnect prompt, a reconnect fixes it, and shelf loading worked the whole time.
4. **Regression checklist** (everything that touches code we changed):
   - [ ] Sign in with Hardcover (new account), sign out and back in.
   - [ ] Link Hardcover from a password account.
   - [ ] Load a Hardcover status shelf and a custom list.
   - [ ] Goodreads CSV import still works.
   - [ ] Existing Goodreads-uploaded spines still show up and can be replaced.
   - [ ] Revoke the app on Hardcover, then confirm shelf loading and search both show the reconnect state.
   - [ ] Rate limiting: type quickly in the frontend and confirm the network tab shows few requests, and that a forced 429 produces the friendly message.
5. **Real-API smoke test (manual, not in CI).** A title on none of the user's shelves, a title with a subtitle, a book with several authors, and a search with no results.

### 10.3 Pre-merge gate (merging deploys the backend)

- [ ] `uv run pytest` passes with Postgres running, and no test is newly skipped.
- [ ] CI passes on the branch.
- [ ] Phase 1 gate done, and sections 10.2 and 12 are checked off.
- [ ] The frontend branch has passed its own gate (frontend plan section 8.3), and the contract check above is done.
- [ ] Deployment order in section 11 is understood, since step 4 removes a route the old frontend uses.

## 11. Deployment order

1. Merge and deploy the backend (new lambda and route, `read:catalog` scope). Existing users are unaffected.
2. Deploy the frontend (it calls `/hardcover/search`).
3. Verify with an existing linked user: Contribute shows the reconnect prompt, then search works after reconnecting.
4. Only after the frontend is live and nothing calls it, deploy the template change that removes `getgrbookdetails` (it can be the same release as step 1 only if the frontend deploys immediately after, because the old bundle calls the route). Confirm the function and route are gone afterwards. If the function was ever created outside the stack, delete it by hand.

## 12. Manual steps and verification

- [ ] Phase 1 gate: real OAuth search works with the final scope string.
- [ ] A test user whose connection predates the scope change gets `hardcover_reauth_required`, not a generic error, and works after reconnecting.
- [ ] Search with the real API for a title on none of the user's shelves, and for a title with a subtitle or several authors.
- [ ] Confirm the production Lambda Python runtime can reach `api.hardcover.app`.
- [ ] After step 4 of the deployment order, confirm `/getgrbookdetails` returns 404 and the function is gone.
- [ ] Revoke any PATs created for the spike.

## 13. Terms and risks

- Catalog search returns public data, not user-owned data, so the Hardcover terms for commercial use of user data aren't triggered. We still store nothing from search results.
- The Hardcover API is in beta. The search action's scope requirement or result shape could change, which is why normalization is defensive and the reauth mapping covers `insufficient_scope`.
- We show no images, so the DMCA policy requirement in the Hardcover docs doesn't apply. Revisit if covers are added later.
- Per-user limit is 60/min with burst 10. The frontend debounce and minimum length keep normal typing well under it. A user who hits `429` sees a friendly message (the frontend plan covers this).

## 14. Open items

- Ranking: does a heavier author weight help the "title + author in one box" case enough, or do we need to re-rank hits ourselves? Decide after the Phase 2 tuning.
- Should compilations or box sets (`compilation: true`) be sorted lower? Not in v1 unless tuning shows it's clearly better.
