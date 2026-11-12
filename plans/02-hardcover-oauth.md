# Plan 2: Hardcover OAuth Sign-In and Library Integration

**Status:** Draft for review
**Status:** Revised after merging `refactor` into `BRIO-35596` (new layout: `lambdas/<name>/handler.py`, shared code in `src/bookshelf/`, template at `infra/template.yaml`).
**Scope:** Backend only (Python Lambdas, DB migrations, SAM changes). No frontend work, but §10 lists the contract the frontend needs.
**Sources:** `~/projects/hardcover-docs` (`api/OAuth.mdx`, `api/OAuth/Getting-Started-Server.mdx`, `api/Getting-Started.mdx`, `schema.graphql`, `capabilities.json`).

## 1. Goal

1. New accounts are created **only** through "Sign in with Hardcover" (OAuth).
2. Existing username/password accounts keep working (legacy), and can **link** a Hardcover account. After linking, they can also sign in with Hardcover.
3. Registration by username/password is turned off.
4. Once signed in, a user's Hardcover library (status shelves and custom lists) can be fetched and turned into the same `{found, unfound}` structure `getgrbookshelf` returns, so shelf generation keeps working.

## 2. Decisions already made

| Decision | Choice |
|---|---|
| Session after OAuth login | **Keep the existing `username` + `authtoken` scheme.** OAuth login mints the same pair, so the ~10 existing lambdas that call `validate_username_authtoken` need no changes. |
| Usernames for new accounts | **Use the Hardcover username, with a numeric suffix on collision** (`alice`, `alice-2`, …). Hardcover's numeric user ID is the stable identity key. |
| Matching books to spines | **Add `hardcover_book_id` to the `bookshelf` table** (and `unfound_to_upload`). |

## 3. What the Hardcover docs establish

**OAuth**

- Standard authorization-code flow with **PKCE (S256) required for every client**, confidential clients included. There is no implicit grant.
- Our app type is **"Web app (server-side)"**, i.e. a confidential client with a `client_secret`. The app type is fixed at creation, so choose carefully.
- Endpoints (also published at `https://api.hardcover.app/.well-known/oauth-authorization-server`, which the docs recommend reading at startup):
  - Authorize (browser): `https://hardcover.app/oauth2/authorize`
  - Token: `POST https://api.hardcover.app/oauth2/token` (HTTP Basic with `client_id:client_secret`, form-encoded)
  - Revoke: `POST https://api.hardcover.app/oauth2/revoke`
  - GraphQL: `https://api.hardcover.app/v1/graphql`
  - Issuer: `https://api.hardcover.app`
- The callback includes `code`, `state` and **`iss`**. We must verify `state` and verify `iss == https://api.hardcover.app` (RFC 9207).
- Access token `hc_at_…` lasts **1 week**. Refresh token `hc_rt_…` lasts **6 months** and **rotates on every use**. If a refresh token is used **twice**, Hardcover treats it as a replay and **revokes the whole chain**, forcing the user through OAuth again. This drives §6.4.
- Redirect URIs must be exact matches (no wildcards) and `https`, except loopback (`http://localhost…`) which is allowed for development.
- There is **no documented `id_token` or userinfo endpoint.** Identity comes from GraphQL `me { id username name }`, which returns an **array** (the docs index `me[0]`) and requires `read:me:content`. The `openid`/`profile` scopes exist ("required for Sign in with Hardcover") but their behaviour isn't documented beyond that. Verify in the spike (§12).
- Consent is remembered for a year per scope set. Users can revoke at `hardcover.app/account/api/authorized-apps`, which kills all our tokens immediately.

**Scopes we need** (the registered scopes are a ceiling; the authorize request picks a subset):

| Scope | Why |
|---|---|
| `read:me:content` | `me { id username name }` for identity |
| `read:library` | `user_books` (implies `:public`, `:private`, `:following`). Could narrow to `read:library:public` plus `:private` if `:following` is unwanted. |
| `read:catalog` | Probably needed for nested `book`/`edition` fields and `book_mappings`. **Verify in the spike**, since the scope tables are keyed on root operations. |

No write scopes are needed.

**API**

- GraphQL over POST with `Authorization: Bearer <token>`. OAuth tokens behave exactly like PATs.
- **Rate limits are per user and shared across all apps and that user's own PATs:** Free = 5,000/day, 60/min, burst 10. Each top-level field costs one request. Nested selections are free.
- Max query time is 30 s. The docs state queries "are not allowed to run in the browser", so everything goes through our Lambda. That is already the architecture.
- Statuses: `1` Want to Read, `2` Currently Reading, `3` Read, `4` Paused, `5` Did Not Finish, `6` Ignored.
- Relevant types: `user_books` (`status_id`, `rating`, `last_read_date`, `book_id`, `edition_id`, `book{…}`, `edition{isbn_10,isbn_13}`), `lists` (`id`, `name`, `books_count`) with `list_books`, `book_mappings` (`platform_id`, `external_id`, `book_id`) and `platforms` (`id`, `name`).
- `books` has `id`, `title`, `release_year`, `cached_contributors`, `cached_image`, `pages`, `slug`. `editions` has `isbn_10` and `isbn_13`.

**Terms of use (needs your eyes):** the API docs say a "commercial product, or publicly accessible website … may not use data owned by users" (libraries, ratings, reviews, lists and so on) *"unless on behalf of a user who has allowed their data to be accessed"*. Our use is user-initiated (the signed-in user builds a shelf from their own library), which fits. Design rules that follow from it:

- Fetch library data per request and **do not store or cache a user's library server-side**.
- Never expose one user's Hardcover data to another user.
- Store only identity (ID, username) and tokens.
- Read the Hardcover Policies page before launch.

Also: the API is **in beta** ("may reset tokens without notice"), so the integration must cope with surprise 401s (§6.4).

## 3a. App registration review

Registered (from the developer app page): redirect URI `https://www.mybookshelf.dev/oauth/callback`; a broad scope ceiling.

- **Add** `http://localhost:3000/oauth/callback`. Loopback `http` is allowed, and without it local dev can't complete the flow. Matching is exact, so also decide whether the site is served at `www.` only. A visit via the apex domain would fail to match.
- **Trim the scope ceiling.** It caps what the app can ever request, and it is what an attacker gets if the client secret leaks. Keep: `read:library`, `read:catalog`, `read:lists` (custom-list shelves), `read:me` (or the narrower `read:me:content` if the form offers it), plus `openid`, `profile` and `offline_access` if the spike shows refresh tokens need them, plus `email` (decided: we want the email address for future use; adding it later would force every user to re-consent). Remove: `read:journal`, `read:goals`, `read:settings`, `read:users`, `read:notifications`, `read:prompts`, `read:social`, `read:vibes`, `read:account`. Request `read:me:email` (implies `read:me:content`) at authorize time. The spike must confirm whether `me.email` needs `read:me:email` alone or also the `email` scope.
- **Final registered ceiling (set):** `read:library`, `read:catalog`, `read:lists`, `read:me`, `openid`, `profile`, `email`, `offline_access`. Authorize request for user sign-in (confirmed by the Phase 0 spike, see §3b): `scope=read:me:email read:library read:lists openid`. `read:catalog` is requested only by the backfill job.
- **App type correction:** the first app was registered as a Single-page app (public client, no secret). The type is immutable, so recreate it as "Web app (server-side)" with the same redirect URIs and scopes, then delete the SPA app. The plan assumes a confidential client (Basic auth on token/refresh/revoke).
- **Confirm the app type** is "Web app (server-side)" (confidential), since it can't be changed afterward, and that **Device Authorization Grant is off**.
- **Fill in** Name, Icon and Website URL, which are shown on the consent screen.
- **Copy the client secret** when first shown (it appears once) into Secrets Manager, not the repo.

## 3b. Phase 0 spike results (run 2026-11-11, real Hardcover API, confidential client)

Flow: authorize -> callback (`code`, `state`, `iss` all present) -> token exchange -> probes -> refresh -> revoke. All succeeded.

| Question | Result |
|---|---|
| Token response | Keys: `access_token`, `refresh_token`, `expires_in` (604800 = 7 days), `scope`, `token_type`, and **`id_token`** (not mentioned in the docs; see below). Granted scope equalled the requested scope exactly. |
| Refresh token issued? | Yes, with `offline_access` requested. Not tested without it, so keep `offline_access`. |
| Identity | `me { id username name }` works. **`me` returns an array.** Hardcover user ID is an int (e.g. 190495). |
| Email | `me { email }` works and returned a value with only `read:me:email` granted. The separate `email` scope was not requested and was not needed. |
| Nested library query | `me { user_books { ... edition { isbn_10 isbn_13 } book { id title release_year cached_contributors } } }` works with `read:library` + `read:catalog` granted. Not tested with `read:library` alone. |
| Pagination | `where status_id`, `order_by id asc`, `limit`/`offset` works. |
| Counts | `me { user_books_aggregate(where: {status_id: {_eq: 3}}) { aggregate { count } } }` works (returned 740 for Read), so the shelf picker can show counts in one request. |
| Custom lists | `me { lists { id name books_count } }` works. |
| Goodreads platform | `platforms` has `{id: 1, name: "goodreads"}` (**lowercase; an exact match on "Goodreads" returns nothing**). Others: 2 librarything, 3 openlibrary, 27 storygraph, 19 amazon. |
| `book_mappings` | **Not tested.** The probe only ran when the exact-name lookup matched. Re-test with `platform_id = 1`. |
| Refresh | Returns a new `access_token` and a **rotated** `refresh_token`, same scope, no `scope` parameter needed. |
| Revoke | HTTP 200. |
| Rate limits | Confirmed as documented: Free = 60/min, burst 10, 5,000/day. Headers: `Ratelimit` and `Ratelimit-Policy`. |

Consequences for the plan:

1. **Author extraction (§6.6):** `cached_contributors` is a JSON list of objects (`author.name`, `contribution`, `primary`, plus role blurbs and author image data), not a string. It is a JSON scalar, so its size can't be trimmed in the query. Pick the first entry with `primary: true`, or `contribution == "Author"`, and use `author.name`. Alternative to test: selecting `book { contributions { author { name } } }` through the relation, which would allow selecting only `name`.
2. **Identity can come from `id_token`.** The token response includes an OIDC-style `id_token` that the docs don't mention. Its claims were not inspected. Check them (names only) before deciding whether to use it. `me` remains a safe, documented fallback and must still be used for the display name.
3. **Scopes:** `read:me:email` alone covers identity plus email at authorize time. The ceiling can keep `email` and `profile`, but the login request doesn't need them beyond `openid`.
4. **Goodreads platform ID is 1.** Use it in the Phase 6 backfill.
5. Open items from round 1 were resolved in round 2 (below).

### Round 2 results (same day; two sign-ins, full scope and a reduced scope)

| Question | Result |
|---|---|
| `id_token` | An RS256 JWT. Header: `alg`, `kid`, `typ`. Claims: **`aud` (our client ID), `auth_time`, `exp`, `iat`, `iss` (`https://api.hardcover.app`), `sub`**. No email, username or name. `sub` was not printed; presumably the Hardcover user ID. Using it needs signature verification against the issuer's JWKS (the `kid` is there; confirm `jwks_uri` in discovery). **Decision: keep using `me { id username name }`.** It is simpler, returns the username we need, and is documented. The `id_token` isn't worth the extra code. |
| Authors | `book { contributions { contribution author { name } } }` works and is far lighter than `cached_contributors`. Books can list several authors, each with `contribution: "Author"`. Use the first entry whose `contribution` is `"Author"` (fallback: first entry) as the `author` string, since Goodreads' `Author` is the first-listed author. |
| `book_mappings` (Goodreads = platform 1) | Works in both directions. **One Hardcover book maps to many Goodreads IDs** (10 or more rows for the first book, one per Goodreads edition). So Goodreads ID to Hardcover ID is many-to-one, which is good for backfill: every spine's Goodreads edition ID resolves to the same Hardcover book. The 500-row cap per request applies to mapping rows, so batch the backfill in groups of about 100 Goodreads IDs. |
| Books inside a list | `me { lists { list_books { book_id book { title } edition { isbn_13 } user_books { rating status_id } } } }` works. `user_books` is an array on each `list_book`; `rating` is a float or null (e.g. `4.0`). |
| `read:library` without `read:catalog` | **Works.** Nested `user_books { book, edition }` returned full data with only `read:library` (plus `read:me:email`, `openid`). |
| `book_mappings` without `read:catalog` | **403** `insufficient_scope`, "Missing scopes: read:catalog". So `read:catalog` is needed only by the backfill job (Phase 6), not by user sign-in. |
| Refresh token without `offline_access` | **Issued anyway.** The refresh grant itself was not retested on that token. Lifetime may differ; unknown. |
| Username characters | One sample (15 lowercase alphanumerics). Not enough to know the rules; keep the sanitising in §6.3. |

Resulting scope decisions:
- **User sign-in scope: `read:me:email read:library read:lists openid`.** Drop `read:catalog` (not needed for users, and a shorter consent screen) and `offline_access` (refresh tokens come back without it). `read:lists` was only exercised under the full scope, so Phase 1 should confirm it is required for `lists`.
- **Registered ceiling:** keep it as set. `read:catalog` stays registered because the Phase 6 backfill needs it; run that job with a token from an account you control.

## 4. What the current backend looks like

Relevant facts from the code:

- `bookshelf_users`: `username` (PK, VARCHAR 50), `hashedPassword NOT NULL`, `email UNIQUE NOT NULL`, `authtoken NOT NULL`, `expiry INT NOT NULL`, `salt NOT NULL`, `ip`, `banned NOT NULL`, `goodreads_id`.
- `lambdas/login_register/handler.py` with helpers in `src/bookshelf/auth.py`: salted SHA-512 password hash; `gen_salt()` is also used to generate the **authtoken**; both use `random.choice` (not a cryptographic RNG). Sessions are stored as a single `authtoken` + `expiry` on the user row, so one session per user.
- Other lambdas authenticate by receiving `username` and `authtoken` and calling `db.validate_username_authtoken`.
- `bookshelf.book_id INT NOT NULL` and `unfound_to_upload.book_id INT NOT NULL` hold the **Goodreads** book ID. `has_username_uploaded_book`, `mark_unfound_as_uploaded` and `get_book_by("book_id")` all key off it.
- `DAO.exec_statement` commits per statement and **swallows exceptions** (returns `False`). There is no transaction API. This matters for §6.4 and for unique-violation handling in §6.2.

Issues found that affect this work (details in §8):

- `get_7_days_from_now()` (`src/bookshelf/auth.py`) computes `now + 7*1000*60*24` = 10,080,000 s ≈ **116 days**, not 7 days.
- The `banned` flag is never checked at login.
- `hash_and_salt(password, None)` raises (AttributeError on `None.encode`) once accounts without a salt exist.

## 5. Data model

All DDL below is valid on Postgres (local) and CockroachDB (prod). Run each `ALTER` as its own statement outside an explicit transaction, because CockroachDB limits schema changes inside transactions. The schema currently lives in two places: `local-dev/migrate.sql` (loaded by docker-compose for local Postgres) and the `create_*_table` methods in `src/bookshelf/dao/cockroachdb_dao.py`. Update both for fresh installs. There is no migration tooling, so add `local-dev/migrations/001_hardcover_oauth.sql` holding only the `ALTER`/`CREATE` statements, run by hand against prod CockroachDB (and against your local DB if it was created before this change). `CREATE TABLE IF NOT EXISTS` will **not** alter existing tables, hence the separate file. CI uses a bare Postgres service with no schema load, so any new integration tests must load `migrate.sql` themselves.

### 5.1 `bookshelf_users`: allow accounts with no password

```sql
ALTER TABLE bookshelf_users ALTER COLUMN hashedPassword DROP NOT NULL;
ALTER TABLE bookshelf_users ALTER COLUMN salt DROP NOT NULL;
ALTER TABLE bookshelf_users ALTER COLUMN email DROP NOT NULL;
```

`email UNIQUE` still permits many NULLs in both Postgres and CockroachDB. **A "legacy" account is defined as `hashedPassword IS NOT NULL`.** No separate flag is needed.

Consequence: Hardcover-only users have no email and no password-reset path. That is acceptable, since Hardcover is the identity provider.

### 5.2 `hardcover_connections` (new)

One row per linked account. Keeping Hardcover state out of `bookshelf_users` leaves that table's shape nearly unchanged.

```sql
CREATE TABLE IF NOT EXISTS hardcover_connections (
  username          STRING PRIMARY KEY REFERENCES bookshelf_users(username),
  hardcover_id      INT UNIQUE NOT NULL,      -- stable identity; the login lookup key
  hardcover_username STRING NOT NULL,         -- display only; refreshed on each login
  access_token_enc  STRING NOT NULL,          -- encrypted, see 6.5
  refresh_token_enc STRING NOT NULL,
  access_expires_at INT NOT NULL,
  scopes            STRING NOT NULL,
  needs_reauth      BOOLEAN NOT NULL DEFAULT false,
  created_at        INT NOT NULL,
  updated_at        INT NOT NULL
);
```

`UNIQUE(hardcover_id)` guarantees one Hardcover account maps to at most one bookshelf account. `PRIMARY KEY(username)` guarantees the reverse.

### 5.3 `oauth_states` (new)

Lambdas are stateless, so the docs' in-memory `pending[state] = verifier` map won't work. Persist it.

```sql
CREATE TABLE IF NOT EXISTS oauth_states (
  state         STRING PRIMARY KEY,
  code_verifier STRING NOT NULL,
  mode          STRING NOT NULL,        -- 'login' | 'link'
  username      STRING NULL,            -- set only for mode='link' (the authenticated account)
  created_at    INT NOT NULL,
  expires_at    INT NOT NULL,           -- created_at + 600
  used          BOOLEAN NOT NULL DEFAULT false
);
```

Expired rows are deleted opportunistically at the start of each `start` call (`DELETE … WHERE expires_at < now`). No scheduler is needed.

### 5.4 `bookshelf` and `unfound_to_upload`: Hardcover book ID

```sql
ALTER TABLE bookshelf ADD COLUMN hardcover_book_id INT NULL;
ALTER TABLE bookshelf ALTER COLUMN book_id DROP NOT NULL;
CREATE INDEX IF NOT EXISTS bookshelf_hardcover_book_id_idx ON bookshelf (hardcover_book_id);

ALTER TABLE unfound_to_upload ADD COLUMN hardcover_book_id INT NULL;
ALTER TABLE unfound_to_upload ALTER COLUMN book_id DROP NOT NULL;
```

**This is the biggest knock-on effect of the spine-matching decision.** A book uploaded by a Hardcover user has no Goodreads ID, so `book_id` must become nullable. Every place that assumes `book_id` is the key must be reviewed:

| Code | Change |
|---|---|
| `CockroachDAO.add_book` (`src/bookshelf/dao/cockroachdb_dao.py`) | Insert `hardcover_book_id`; accept a missing `book_id` |
| `DAO.has_username_uploaded_book(username, book_id)` | Take either ID (match whichever is present) |
| `DAO.has_user_saved_unfound`, `mark_unfound_as_uploaded` | Same |
| `DAO.get_book_by("book_id", …)` in `add_unfound_to_uploads` | Same |
| `DAO.add_unfound_to_upload` | Insert `hardcover_book_id` |
| `DAO.format_book_tuple` / `format_unfound_to_upload_tuple` | **Positional tuple indexing.** `SELECT *` order changes when a column is appended. New columns are added at the end, but `format_book_tuple` currently ignores `timestamp` at index 14, so add `hardcover_book_id` at the *next* index (the tuple is built in `format_book_tuple` and `format_unfound_to_upload_tuple`) and confirm the column order on both DBs. |
| `lambdas/upload_spine/handler.py` `create_filename(title, book_id, ext)` | The filename embeds `book_id`. Fall back to `hc<hardcover_book_id>` when there is no Goodreads ID. |
| `lambdas/upload_spine/handler.py` required-field list | `book_id` is currently required. Require **either** ID. |
| `get_book_batch` | Includes `book_id IN (…)`; extend with `hardcover_book_id` |

Existing spines have `hardcover_book_id = NULL`, so on day one they can only be matched by title and author. §7 Phase 6 backfills them.

## 6. Design

### 6.1 Shape: backend-for-frontend

The registered redirect URI points at a **frontend route**: `https://www.mybookshelf.dev/oauth/callback` (prod) and `http://localhost:3000/oauth/callback` (dev). This is separate from the backend API routes named `/auth/hardcover/*` below. Hardcover redirects the browser to `/oauth/callback` with `code`, `state` and `iss`. The frontend forwards those three values to our `callback` Lambda, which holds the secret and the PKCE verifier. Neither the client secret nor the verifier ever reaches the browser.

```
Browser            Frontend (React)        Lambda: start/callback        Hardcover
  |  click "Sign in" |                           |                           |
  |----------------->|-- POST /auth/hardcover/start {mode} ---------------->|
  |                  |<-- {authorize_url, state} -- stores state+verifier    |
  |<-- redirect to authorize_url ------------------------------------------>|
  |                          user approves on hardcover.app                  |
  |<-- redirect: /auth/hardcover/callback?code&state&iss                     |
  |----------------->|-- POST /auth/hardcover/callback {code,state,iss} --->|
  |                  |                           |-- POST /oauth2/token --->|
  |                  |                           |-- POST graphql me ------>|
  |                  |<-- {username, authtoken}  (same shape as login) -----|
```

### 6.2 Endpoints

All use `http_result(status, body)` from `src/bookshelf/http.py`. That sets the real HTTP status and also wraps `{"statusCode", "body"}` inside the JSON body, which is what the frontend reads today. Errors from newer handlers use `{"error": "message"}` as the body (as the CSV importer does); older ones return a bare string, so keep the `error` object form for new endpoints. Endpoints take **POST bodies** (not query strings) for anything involving secrets or tokens.

**`POST /auth/hardcover/start`**

Request: `{"mode": "login"}` or `{"mode": "link", "username": "...", "authtoken": "..."}`.

1. For `link`, call `validate_username_authtoken`. The account must be authenticated, and its username is stored on the state row, binding the pending link to *that* account.
2. Generate `state` (24 random bytes) and `code_verifier` (32 random bytes, giving 43 base64url characters; RFC 7636 needs 43–128), both from `secrets`. Compute `code_challenge = base64url(sha256(verifier))`.
3. Insert the `oauth_states` row with a 10-minute expiry.
4. Return `{"authorize_url": "...", "state": "..."}` where the URL has `response_type=code`, `client_id`, `redirect_uri`, `state`, `code_challenge`, `code_challenge_method=S256` and `scope`.

**`POST /auth/hardcover/callback`**

Request: `{"code", "state", "iss"}`, or `{"error", "error_description", "state"}` if the user denied consent.

1. If `error` is present: consume the state row and return 400 with a friendly message.
2. Verify `iss == "https://api.hardcover.app"`.
3. **Atomically consume the state:** `UPDATE oauth_states SET used=true WHERE state=%s AND used=false AND expires_at>%s RETURNING code_verifier, mode, username`. Zero rows means 400 "expired or already used". The atomic update, not a read-then-write, is what prevents replay.
4. Exchange the code at the token endpoint (Basic auth, `grant_type=authorization_code`, `code`, `redirect_uri` exactly matching the one in `start`, `code_verifier`). The most common first-run failure is a `redirect_uri` that differs from the registered one.
5. Call `me { id username name }` with the new access token, taking `me[0]`.
6. Branch on mode:

   **`login`**
   - Look up `hardcover_connections` by `hardcover_id`.
   - *Found:* load the user, reject if `banned`, update the stored tokens and `hardcover_username`, mint a session.
   - *Not found:* **create a new account** (§6.3), insert the connection, mint a session.

   **`link`**
   - Re-validate that the `username` stored on the state row still exists.
   - If `hardcover_id` is already linked to a **different** account, return 409 `hardcover_already_linked`. Never silently merge two accounts.
   - If this account already has a *different* Hardcover ID linked, return 409 (require an explicit unlink first, which is out of scope).
   - Otherwise insert/update the connection. Do **not** mint a new session; return `{linked: true, hardcover_username}`.

7. Return the same shape the login lambda returns today: `{"username", "authtoken", "goodreads_id"}`, plus `{"hardcover_username", "is_new_account"}` for the frontend.

**`GET`/`POST /hardcover/shelves`** and **`/hardcover/shelf`**: see §6.6.

**`POST /logout`**: invalidates the session (set `expiry` to now) and revokes the Hardcover refresh token at `/oauth2/revoke` (the docs recommend this so the user's "Authorized apps" page doesn't show a stale session). Today logout only deletes browser cookies, so the server-side token stays valid until it expires.

### 6.3 Creating an account for a new Hardcover user

1. Candidate username = Hardcover username, restricted to `[A-Za-z0-9_.-]` (replace anything else with `_`) and truncated to 50 characters. The username is used in S3 keys and as `submitter`/`owner` everywhere, so it must be safe in those places.
2. **Case-insensitive uniqueness check.** `get_user` is an exact match, so `Alice` and `alice` could both exist today. Check `LOWER(username) = LOWER(%s)` so a new account can't be confused with a legacy one.
3. On a clash try `-2`, `-3`, … (bounded, say 50 attempts).
4. If the Hardcover `me.email` is available and not already in `bookshelf_users` (case-insensitive), store it; otherwise store NULL. `email` is `UNIQUE`, and because the DAO swallows errors, a clash would otherwise make the whole insert fail silently. Never link or merge accounts by email: legacy emails were never verified.
5. Insert with `hashedPassword = NULL`, `salt = NULL`, `email = NULL`, `banned = FALSE`, a fresh authtoken and expiry. Because `exec_statement` swallows errors, a concurrent insert of the same username returns `False` rather than raising. Treat `False` as "taken" and retry with the next suffix, then re-read to confirm.
6. **Never auto-link by name or email.** A Hardcover user called `alice` is not the same person as a legacy user `alice`. Merging happens only through the authenticated `link` flow.

### 6.4 Token storage, refresh and the rotation hazard

Access tokens live a week, so we must refresh server-side when building shelves days or weeks after login. The danger: **refresh tokens rotate on use, and a double-use revokes the whole chain.** Two concurrent Lambda invocations (e.g. a user double-clicking, or two browser tabs) could both read the same refresh token and both spend it.

Rules for `hardcover_client.get_valid_access_token(db, username)` (`src/bookshelf/hardcover_client.py`):

1. If `access_expires_at` is more than 60 s away, use the stored access token.
2. Otherwise refresh **under a row lock.** This needs a real transaction: `SELECT … FROM hardcover_connections WHERE username=%s FOR UPDATE`, call the token endpoint, `UPDATE` the new tokens, `COMMIT`. The existing DAO has no transaction API, so add a `with db.transaction() as cur:` context manager that issues no intermediate commits. A second invocation then blocks on the lock and, after acquiring it, re-reads the already-refreshed token and skips the refresh.
3. **Always persist the new refresh token before using the new access token.** If the process dies between the HTTP response and the DB write, the old token is spent and the new one is lost. That case is unrecoverable, so mark `needs_reauth = true` and surface it.
4. **Never blindly retry a refresh request** that timed out. It may have succeeded server-side, and a retry would be a replay. On ambiguity, set `needs_reauth`.
5. On `invalid_grant`, a 401 from the GraphQL endpoint (revoked, or a beta token reset), or `needs_reauth`: return `{"statusCode": 401, "body": {"error": "hardcover_reauth_required"}}`. The frontend then runs the `start` flow again. This does **not** invalidate our own session. The user stays signed in to the site.
6. If the refresh grant omits `scope`, the old scopes are reused (per the docs). Do not pass scope on refresh.

### 6.5 Encrypting stored tokens

A refresh token is a six-month credential to a user's whole Hardcover library, so a DB leak must not expose usable tokens.

- Encrypt with **AWS KMS** (`kms.encrypt` / `kms.decrypt` directly, since tokens are far below the 4 KB limit). boto3 is already in the layer, so no new native dependency is needed. Use an `EncryptionContext` of `{"username": …}` so a ciphertext copied to another row won't decrypt.
- Lambda role gets `kms:Encrypt` and `kms:Decrypt` on that one key.
- **Local dev:** LocalStack provides KMS. Per the existing local-dev lesson, don't rely on the global `AWS_ENDPOINT_URL`, because the host `.env` leaks into Lambda containers. (Note the committed `.env` on this branch sets `AWS_ENDPOINT_URL=http://localhost:4566`, and `local-dev/env.json` also sets it.) Add a service-specific `KMS_ENDPOINT_URL` env var, wired like `S3_ENDPOINT_URL` (a template parameter plus a `Globals` env var, with `make local` passing `host.docker.internal:4566`), and change `SERVICES: s3` to `SERVICES: s3,kms` in `local-dev/docker-compose.yml` (LocalStack 2.3 supports KMS).
- Keep this behind a tiny `src/bookshelf/token_crypto.py` (`encrypt(username, plaintext)` / `decrypt(username, blob)`), so the backend can be swapped for a local-only key in tests.

### 6.6 Fetching a library: Hardcover to `{found, unfound}`

Two lambdas, authenticated with `username` + `authtoken` in the POST body.

**`/hardcover/shelves`** returns what the user can pick:

```graphql
query {
  me {
    id
    status_counts: user_books_aggregate(where: {status_id: {_eq: 3}}) { aggregate { count } }   # repeat per status, aliased
    lists { id name books_count }
  }
}
```

Each aliased top-level field costs one request, but these are nested under `me`, so the whole query costs **1**. Verify the exact aggregate field names in the spike. If aggregates aren't exposed under `me`, fetch `lists` and compute counts lazily.

Response: `{"shelves": [{"id": "status:3", "name": "Read", "count": N}, {"id": "list:456", "name": "My Favs", "count": M}, …]}`.

**`/hardcover/shelf`** takes `{"shelf": "status:3"}` or `{"shelf": "list:456"}`:

```graphql
query ($status: Int!, $limit: Int!, $offset: Int!) {
  me {
    user_books(where: {status_id: {_eq: $status}}, order_by: {id: asc}, limit: $limit, offset: $offset) {
      rating
      last_read_date
      book_id
      edition { isbn_10 isbn_13 }
      book { id title release_year contributions { contribution author { name } } }
    }
  }
}
```

- Page with `limit: 500` and increasing `offset`, using a stable `order_by`, until a page returns fewer than `limit`. A 1,400-book shelf costs 3 requests of the 5,000/day budget.
- Lists use `list_books(where: {list_id: …}) { book {…} edition {…} }` plus a join to the user's own `user_books` for rating. Verify the shape in the spike.
- Map each row to the existing book shape: `title`, `author` (first `contributions` entry with `contribution == "Author"`, `author.name`), `isbn`, `isbn13` (from the edition), `pubDate` (`release_year`), `user_rating` (`rating`, which is a float where Goodreads used an int, so round or scale as the frontend expects), `user_read_at`, plus **`hardcover_book_id`** (`book.id`). `book_id` is absent here.
- Handle `me` being an array.
- Raise this Lambda's timeout to 60 s. Hardcover's own max query time is 30 s and we may page several times.
- Respect rate limits: read the `RateLimit` headers; on 429, return 429 with a "try again shortly" body rather than looping.
- **Do not cache the library.** See the terms note in §3.

**Matching** extends `which_books_found(db, bookList)` in `src/bookshelf/bookshelf.py` (shared with the CSV importer, so keep its signature and behaviour for Goodreads input unchanged; `bookshelf.py` also contains deprecated shelf-image code, so consider moving the matching helpers to `src/bookshelf/matching.py` as a separate cleanup):

1. Match spines on `hardcover_book_id` first.
2. Fall back to title and author (existing logic), which is how pre-existing, un-backfilled spines match.
3. Keep "prioritise an exact ID match to the top" semantics, now for `hardcover_book_id`.

The fallback uses the first contribution's `author.name`. Spot-check a few against the Goodreads `author` values already stored in `bookshelf.author` (initials, diacritics, "Last, First" ordering) before relying on title+author matching.

## 7. Phases

Each phase is independently deployable and leaves the system working.

**Phase 0: Spike and registration (about half a day)**
- Create the Hardcover developer app: **Web app (server-side)**. Redirect URIs: `https://www.mybookshelf.dev/oauth/callback` and `http://localhost:3000/oauth/callback`. Device grant **off**. Scopes: trim the ceiling to the §3 list after the spike.
- With a throwaway script, run the full flow against localhost and answer: Does `read:library` alone return `book { title … }`? Which scopes does `book_mappings` need? Is a refresh token issued without `offline_access`? What does `user_books_aggregate` look like under `me`? What is the Goodreads `platforms.id`?
- Record the answers in this plan. **Nothing else starts until the scope questions are settled.**

**Phase 1: Foundations**
- `local-dev/migrations/001_hardcover_oauth.sql` (§5.1–5.4) plus matching updates to `local-dev/migrate.sql` and the `create_*_table` methods, applied to local Postgres first.
- Add `mint_session(db, username)` to `src/bookshelf/auth.py` (returns `{username, authtoken, expiry}`), and use it from `lambdas/login_register/handler.py` too.
- Fix token generation to use `secrets` (§8).
- Add DAO methods: `get_user_by_hardcover_id`, `create_oauth_user`, `upsert_hardcover_connection`, the `oauth_states` helpers, a case-insensitive `username_taken`, and the `transaction()` context manager.
- Add `src/bookshelf/token_crypto.py` plus the KMS key and LocalStack wiring.

**Phase 2: OAuth sign-in and account creation**
- `src/bookshelf/hardcover_client.py`: discovery (cached in a module global, falling back to the hardcoded constants), `build_authorize_url`, `exchange_code`, `refresh`, `graphql(query, vars, token)`, `revoke`. Use `urllib.request` with explicit timeouts, so no new layer dependency.
- `lambdas/hardcover_auth_start/handler.py` and `lambdas/hardcover_auth_callback/handler.py` for `login` mode. Use `parse_event` and `http_result` from `src/bookshelf/http.py`, and the same lazy `_get_db()` pattern as the other handlers (this also makes them patchable in tests).
- `lambdas/logout/handler.py`.
- `infra/template.yaml`: new functions, and parameters/env `HARDCOVER_CLIENT_ID`, `HARDCOVER_REDIRECT_URI`, `KMS_KEY_ID`, `KMS_ENDPOINT_URL`. **Client secret handling mirrors the existing cert pattern** (`SKIP_SSL_CERT` / `CERT_SECRET_ARN`): in prod set `HARDCOVER_SECRET_ARN` (Secrets Manager, resolved from SSM like `CertSecretArn` in `make deploy`) and fetch the secret once per cold start; for local dev a `NoEcho` template parameter `HardcoverClientSecret` is passed from your shell by `make local`. **Do not put the secret in `local-dev/env.json` or `.env`: both are tracked by git on this branch.** Gitignore a separate `local-dev/secrets.local.env` if you want a file.

**Phase 3: Account linking and registration shutdown**
- `link` mode in `start` and `callback`, with the 409 cases.
- `lambdas/login_register/handler.py`:
  - `register` returns 403 (or 410) with `"New accounts are created by signing in with Hardcover."`
  - `login` rejects accounts where `hashedPassword IS NULL` (generic failure message, no 500), and checks `banned`.
- Keep `login` working for legacy users, linked or not.

**Phase 4: Hardcover library to shelves**
- `lambdas/get_hardcover_shelves/handler.py` and `lambdas/get_hardcover_shelf/handler.py` (§6.6), with `get_valid_access_token` and the locked refresh.
- Extend `which_books_found` with `hardcover_book_id`.

**Phase 5: Spine upload and queue support for Hardcover IDs**
- `lambdas/upload_spine`, `lambdas/add_unfound_to_upload`, `lambdas/get_unfound_to_upload` and the DAO methods accept `hardcover_book_id` (§5.4 table). Without this, a Hardcover user can generate shelves but can't contribute spines for books nobody has uploaded yet.

**Phase 6: Backfill existing spines with `hardcover_book_id`**
- One-off script (not a Lambda): for all `bookshelf` rows with a Goodreads `book_id` and no `hardcover_book_id`, query `book_mappings(where: {platform_id: {_eq: <goodreads>}, external_id: {_in: […]}}) { external_id book_id }` in batches (row cap is 500 per request, rate limit 60/min per token).
- Needs a catalog-capable token. Use a PAT or OAuth token belonging to a Hardcover account we control. This is catalog data (not user data), so the terms note doesn't apply.
- Spines whose Goodreads ID has no mapping stay NULL and keep matching by title and author.
- Without this phase, the existing community spine library is effectively invisible to Hardcover users except via title matching. **Treat it as required for launch quality.**

**Phase 7: Cleanup**
- Nothing to do for `feedparser`: Plan 1 §4.10 removes it.

## 8. Fixes to existing auth code to make along the way

These touch code we'll already be editing. Items 1 and 2 matter more once OAuth accounts exist.

1. **`random.choice` for salts and authtokens** is not cryptographically secure. Switch to `secrets.token_urlsafe(32)` in `src/bookshelf/auth.py` (`gen_salt` is used for both salts and authtokens, so add a separate `gen_authtoken`). Existing tokens keep working, since they're only compared for equality.
2. **`banned` is never enforced.** Check it in both login paths, and in `validate_username_authtoken` if you want banned users cut off mid-session.
3. **Session lifetime bug. DECIDED: 30 days.** `7*1000*60*24` seconds is about 116 days, not 7 (the old formula was wrong). Replace it with a `SESSION_TTL_SECONDS = 30 * 24 * 60 * 60` constant in `src/bookshelf/auth.py`, used for both password and OAuth sessions. That shortens new sessions from about 116 days to 30; existing sessions are unaffected until they expire. The Hardcover access token lasts 7 days, but our session is independent of it, and the refresh token (6 months) keeps library access working across the session.
4. **`hash_and_salt(password, None)`** crashes for OAuth-only users. Guard with `if not user["hashedPassword"]: return generic failure`.
5. **User enumeration.** Login says `username 'x' does not exist` vs `invalid password`. Use one message.
6. **Authtoken in query strings.** `/validate` takes `username` and `authtoken` as GET params, which land in API Gateway access logs. All *new* endpoints use POST bodies. Moving `/validate` is optional follow-up.
7. **Dynamic SQL column names.** `update_user_col` and `get_user_by` concatenate a column name into SQL. Every current caller passes a literal, but don't reuse them with request-derived input. The new DAO methods use fixed SQL.

## 9. Testing

**Where tests go:** parser/crypto/PKCE helpers in `tests/unit/`; handlers in `tests/handler/`, following `tests/handler/test_login_register.py` (patch `bookshelf.dao.cockroachdb_dao.psycopg2.connect`, patch the handler's `_get_db`). Mock the Hardcover HTTP layer by patching `hardcover_client`'s single request function. Run with `make test` and `make lint`. The refresh-concurrency test needs a real Postgres loaded with `local-dev/migrate.sql`; CI provides a bare Postgres service, so the test must load the schema itself.

**Unit (mock HTTP and DB):**
- PKCE: challenge equals `base64url(sha256(verifier))` with no padding, and the verifier length is 43–128.
- Callback: bad `state`, reused `state` (second call fails), expired `state`, wrong `iss`, `error=access_denied`, token-endpoint 400 (`redirect_uri` mismatch), `me` returning an empty array.
- Account creation: clean username; clash with a legacy user (case-insensitive) gets `-2`; many clashes; concurrent insert (DAO returns False) retries; illegal characters sanitised; over-length truncated.
- Login: existing connection logs in; banned user is rejected; `hardcover_username` change is stored while `username` stays frozen.
- Link: success; `hardcover_id` already on another account gives 409; link requires a valid session; state row bound to the right account; a stolen `state` can't be linked by a different logged-in user.
- Legacy: `register` is refused; password login still works for legacy; OAuth-only user can't password-login (no 500).
- Refresh: skip when fresh; refresh persists the new refresh token; `invalid_grant` sets `needs_reauth` and returns `hardcover_reauth_required`; **two simultaneous refreshes spend the refresh token exactly once** (integration test against local Postgres with two threads).
- Crypto: round-trip; ciphertext from user A fails to decrypt under user B's context.
- Shelf fetch: pagination across 3 pages; `me` array handling; 429 propagation; rating and author mapping.
- Matching: `hardcover_book_id` match outranks title match; NULL-ID legacy spine still matches by title and author.

**Integration / manual:**
- Full flow on localhost with the loopback redirect URI against the real Hardcover (a throwaway account is fine).
- Revoke the app at hardcover.app and confirm the next library fetch returns `hardcover_reauth_required` and the site session survives.
- Run the migration on a copy of prod data (or a Cockroach dev cluster) before touching production, and confirm `format_book_tuple` still maps columns correctly.

## 10. Frontend contract (for later)

| Need | Endpoint |
|---|---|
| "Sign in with Hardcover" button | `POST /auth/hardcover/start {mode:"login"}` then redirect to `authorize_url`. Store `state` in `sessionStorage`. |
| Callback route | Compare URL `state` to `sessionStorage` **before** calling the backend (blocks login-CSRF where an attacker feeds a victim their own callback URL). Then `POST /auth/hardcover/callback {code,state,iss}`. Store `username`/`authtoken` exactly as the password login does today. |
| "Link Hardcover" button in Profile | `POST /auth/hardcover/start {mode:"link", username, authtoken}` |
| Handle `hardcover_reauth_required` | Re-run the `start` flow (mode matches the user's situation) |
| Shelf picker / generation | `/hardcover/shelves`, `/hardcover/shelf` |
| Login page for legacy users | Keep the password form; remove the "register" tab |
| Messaging | "Already have a bookshelf account? Log in with your password, then link Hardcover in your profile." Otherwise a legacy user who clicks "Sign in with Hardcover" gets a **second, empty** account. |

## 11. Open questions

- **Q1. Scope set.** Do you want `read:library` (which includes `:following`) or only `:public` + `:private`? Resolved in the Phase 0 spike, but it affects what the consent screen shows users. Also trim the registered ceiling (see §3a).
- **Q2. Unlinking. RESOLVED: not needed.** (Original note:) Should a user be able to unlink Hardcover? For an OAuth-only account that would lock them out, so it would be allowed only for legacy accounts that still have a password. I've left it out; say if you want it.
- **Q3. Legacy sunset. RESOLVED: legacy passwords live forever.** The password login path stays permanently. No sunset work is planned.
- **Q4. Merging a second account.** A legacy user who already created a separate Hardcover-based account before linking will have two accounts. Merge tooling (re-point `submitter`/`owner` rows) is not in this plan. How common do you expect that to be?
- **Q5. Hardcover username format.** The docs don't state Hardcover's username rules. The sanitising in §6.3 is defensive. Confirm what characters real usernames contain.
- **Q6. Terms.** Please read Hardcover's Policies page and confirm the use case (§3) is acceptable, especially since the site is public.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Refresh-token double-spend revokes a user's connection | Row lock plus transactional refresh (§6.4); never auto-retry a refresh |
| Hardcover API is in beta and may reset tokens | `hardcover_reauth_required` path; site session independent of Hardcover token validity |
| Per-user rate limits shared with their other apps | Page conservatively; surface 429; don't poll |
| `book_id` going nullable breaks code that assumed it | The §5.4 audit table, plus tests that insert Hardcover-only spines through every path |
| Existing spines unmatched until backfilled | Phase 6; title and author fallback in the meantime |
| Username collisions and look-alikes | Case-insensitive check; no auto-linking; suffixing |
| User loses access if Hardcover goes away or they delete their account | OAuth-only accounts have no fallback. Accept for now, and revisit with Q2/Q3. |
| Deploy pipeline isn't ready (`docs/TODO-setup-aws-deploy.md`): production lambdas are still deployed by hand, `make deploy` has no stack name and CI's deploy job has no AWS secrets | Decide whether the Hardcover functions ship via manual zip like the rest, or wait for the SAM stack. Either way the prod migration, KMS key and Secrets Manager entry are manual steps. |
| Positional `SELECT *` tuple mapping in DAO | Add columns last, update `format_*` indexes, test on both Postgres and Cockroach |

## 13. Out of scope

Frontend work; unlinking; account merging; using Hardcover write scopes (e.g. pushing shelves back); email or password recovery for OAuth-only accounts; the device-code flow; moving `/validate` off query strings.
