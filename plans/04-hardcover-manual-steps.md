# Hardcover OAuth: Manual Steps Remaining

The backend for `plans/02-hardcover-oauth.md` is written and tested with mocks (155 tests pass, 1 skipped), but it is **not committed and has never run against a live service**. Everything below is work only you can do: committing, local verification, AWS resources, a production database migration, deployment, and the frontend. Steps are in suggested order. Do not skip Part B: several behaviours (the row-lock refresh, list shelves, revoked-token handling) have never been exercised for real.

## Part A: Commit the work

- [ ] Review the diff, then commit in logical chunks. Suggested split (from the implementation report):
  1. **Foundations:** `local-dev/migrations/001_hardcover_oauth.sql`, `local-dev/migrate.sql`, `local-dev/docker-compose.yml`, `src/bookshelf/dao/cockroachdb_dao.py`, `src/bookshelf/auth.py`, `src/bookshelf/token_crypto.py`, `tests/conftest.py`, `tests/fakes.py`, and their unit tests
  2. **OAuth sign-in:** `src/bookshelf/hardcover_client.py`, `hardcover_accounts.py`, `lambdas/hardcover_auth_start/`, `hardcover_auth_callback/`, `logout/`, `infra/template.yaml`, `Makefile`, and tests
  3. **Linking and registration shutdown:** `lambdas/login_register/handler.py`, `tests/handler/test_login_register_legacy.py`
  4. **Library to shelves:** `src/bookshelf/hardcover_library.py`, `hardcover_http.py`, `bookshelf.py`, `lambdas/get_hardcover_shelves/`, `get_hardcover_shelf/`, and tests
  5. **Spine and queue support:** `lambdas/upload_spine/`, `lambdas/add_unfound_to_upload/`, and tests
  6. **Backfill script:** `local-dev/scripts/backfill_hardcover_ids.py`
  
  The OAuth callback handler contains both login and link modes; splitting those would mean separating `_handle_link`.
- [ ] Commit `plans/02-hardcover-oauth.md` and `plans/04-hardcover-manual-steps.md` too, if you want the plans in git.
- [ ] Commit message prefix needs the ticket type for BRIO-35596 (`feat:` for a story, `fix:` for a bug). I can't look it up.
- [ ] Skim the "behaviour changes" list in Part E before committing; item 1 changes shared database behaviour for **every** lambda.

## Part B: Verify locally before touching AWS

These need Docker running (your Makefile expects the Colima socket).

- [ ] **Run the row-lock test, which has never run:**
  ```
  make dev
  uv run pytest tests/integration -rs
  ```
  It must pass, not skip. It checks that two simultaneous token refreshes spend the refresh token exactly once. If it fails, stop: a double-spend revokes the user's whole Hardcover connection.
- [ ] **Start LocalStack with KMS.** `docker-compose.yml` now sets `SERVICES: s3,kms`, so recreate the container (`docker compose -f local-dev/docker-compose.yml up -d --force-recreate localstack`). Then create a local key:
  ```
  aws --endpoint-url http://localhost:4566 --region us-east-1 kms create-key
  ```
  Note the `KeyId` in the output. (LocalStack accepts dummy credentials such as `test`/`test`.)
- [ ] **Apply the migration to your local database** if it was created before this change (a fresh `make dev` already loads `migrate.sql`):
  ```
  psql postgresql://postgres:dev@localhost:5432/bookshelf -f local-dev/migrations/001_hardcover_oauth.sql
  ```
- [ ] **Run the whole stack with real Hardcover.** In the terminal where you run `make local`:
  ```
  export KMS_KEY_ID=<KeyId from above>
  export HARDCOVER_CLIENT_ID=a062038b-5d7e-4646-ace2-e250b8457cc4
  export HARDCOVER_CLIENT_SECRET=[YOUR-CLIENT-SECRET]
  make local
  ```
  Leave out the brackets when you type the secret. The command is not echoed by `make`, but the secret **is visible in the process arguments** on your machine while SAM runs. That's acceptable on a personal laptop; don't do it on a shared one.
- [ ] **Run the frontend on port 3000** with a `/oauth/callback` route (Part D) and walk through: sign in, new account created; sign out and in again, same account; link from a legacy account; build a Hardcover shelf.
- [ ] **Test the cases the mocks can't prove:**
  1. **Revoked app:** revoke the app at `hardcover.app/account/api/authorized-apps`, then request a shelf. Expect HTTP 401 `hardcover_reauth_required` and the site session still valid. The agent flagged that a Hardcover reply of HTTP 200 containing an auth error would **not** be detected; confirm what Hardcover actually returns.
  2. **List shelves:** the query for books inside a custom list is marked `TODO(live)` in `src/bookshelf/hardcover_library.py` because it was never tested with variables. Request a list shelf and check the result.
  3. **Large shelf:** your `Read` shelf has about 740 books (2 to 3 pages). Check time and rate-limit headers.
  4. **Username clash:** make a legacy account whose username matches a Hardcover username and confirm the new Hardcover account gets `-2`.
  5. **Link conflicts:** try to link one Hardcover account to two bookshelf accounts; expect 409 `hardcover_already_linked`.
  6. **Banned:** set `banned` on a test user and confirm password login and an existing session are both refused.
- [x] **Template validation (done):** `sam validate --template infra/template.yaml` reports a valid SAM template. With `--lint`, the only finding is the old `nodejs20.x` runtime on `GetGRBookDetailsFunction` (W2531), which predates this work and is listed in `docs/TODO-setup-aws-deploy.md`. It was run with dummy credentials, so no AWS account was involved.
- [ ] **Still to do:** `sam build --template infra/template.yaml` (needs Docker and a Python 3.12 layer build) to confirm the functions and layer package.

## Part C: AWS resources (production)

I have not created or changed anything in AWS. Replace placeholders in brackets (without the brackets). Use your normal profile and region.

- [ ] **KMS key** for encrypting stored tokens:
  ```
  aws kms create-key --description bookshelf-hardcover-tokens
  aws ssm put-parameter --name /bookshelf/kms_key_id --type String --value [KeyId]
  ```
- [ ] **Client secret** in Secrets Manager. Enter it from a file or an interactive prompt that is not tracked by git, never inline in a shared shell history:
  ```
  aws secretsmanager create-secret --name bookshelf/hardcover-client-secret --secret-string file://[path-to-untracked-file]
  aws ssm put-parameter --name /bookshelf/hardcover_secret_arn --type String --value [secret ARN]
  aws ssm put-parameter --name /bookshelf/hardcover_client_id --type String --value a062038b-5d7e-4646-ace2-e250b8457cc4
  ```
  Delete the local file afterwards.
- [ ] **IAM:** if you deploy with SAM, the shared `HardcoverAccessPolicy` in the template grants KMS `Encrypt`/`Decrypt` on that one key and `GetSecretValue` on that one secret. If you zip functions by hand instead (see below), attach equivalent permissions to each function's role yourself: it needs these for the callback, logout, shelves and shelf functions. The start function needs neither.
- [ ] **Hardcover app settings:** confirm `https://www.mybookshelf.dev/oauth/callback` and `http://localhost:3000/oauth/callback` are both registered. Both already are, per the earlier setup.

## Part D: Production database migration

Do this **before** deploying any new code, and take a backup or snapshot first.

- [ ] Back up or snapshot the CockroachDB cluster (or at least the `bookshelf`, `unfound_to_upload` and `bookshelf_users` tables).
- [ ] Run each statement in `local-dev/migrations/001_hardcover_oauth.sql` **one at a time, outside an explicit transaction**, in the Cockroach SQL shell. CockroachDB limits schema changes inside transactions. Every statement is safe to re-run.
- [ ] Verify that the DAO's position-based column mapping still holds. `SELECT * FROM bookshelf LIMIT 1;` must show `hardcover_book_id` as the **last** column (index 15), and `SELECT * FROM unfound_to_upload LIMIT 1;` must show it at index 10. If the order differs, stop and tell me; the DAO would silently misread rows.
- [ ] Verify existing logins still work: sign in with a legacy account before and after the migration.

## Part E: Deploy

`docs/TODO-setup-aws-deploy.md` says nothing deploys from this repo yet. Decide between finishing the SAM stack or zipping by hand, exactly as in `plans/03-goodreads-csv-manual-steps.md` (Part 1 there). With SAM, `make deploy` now passes the SSM-resolved `HardcoverClientId`, `HardcoverSecretArn`, `KmsKeyId` and the production redirect URI, but it still lacks a stack name, an artifacts bucket and capabilities (the TODO file lists these).

New or changed functions and routes:

| Function | Route | Notes |
|---|---|---|
| `hardcoverAuthStart` | `POST /auth/hardcover/start` | no secret needed |
| `hardcoverAuthCallback` | `POST /auth/hardcover/callback` | needs secret, KMS |
| `logout` | `POST /logout` | needs secret, KMS |
| `getHardcoverShelves` | `POST /hardcover/shelves` | timeout 60 s |
| `getHardcoverShelf` | `POST /hardcover/shelf` | timeout 60 s, 512 MB |
| `loginRegister`, `uploadSpine`, `addUnfoundToUpload` | existing routes | updated code |

- [ ] If deploying by hand: build and publish a new layer version (it now includes `token_crypto.py`, `hardcover_*.py`, and the changed `auth.py`, `bookshelf.py`, `dao/cockroachdb_dao.py`). Attach it to **every** function that uses the DAO (all of them), because the DAO change below affects everything.
- [ ] Environment variables per function: the existing ones plus `HARDCOVER_CLIENT_ID`, `HARDCOVER_REDIRECT_URI` (`https://www.mybookshelf.dev/oauth/callback`), `KMS_KEY_ID`, and on the four secret-using functions `HARDCOVER_SECRET_ARN`. Leave `HARDCOVER_CLIENT_SECRET` unset in production, and `KMS_ENDPOINT_URL` unset.
- [ ] API routes: use **Lambda proxy integration** (as for the CSV route) and enable CORS with `POST` and `OPTIONS`, header `Content-Type`. Deploy the API stage afterwards.
- [ ] Check the API Gateway stage does **not** log full request/response bodies: these requests carry authorization codes and session tokens.
- [ ] Deploy the lambdas in this order: migrate the database, then the layer and functions, then the API routes, then the frontend.

## Part F: Backfill existing spines

Without this, existing community spines match Hardcover users only by exact title and author.

- [ ] Create a Hardcover **personal access token** with the `read:catalog` scope, from `hardcover.app/account/api`. It reads catalog data, not anyone's private library.
- [ ] Dry run first (writes nothing):
  ```
  export DATABASE_URL=[connection string]
  export HARDCOVER_TOKEN=[the PAT]
  uv run python local-dev/scripts/backfill_hardcover_ids.py
  ```
  For production CockroachDB add `--sslrootcert [path to ca.crt]`.
- [ ] Read the dry-run summary (how many spines map, how many don't, how many Goodreads IDs map to more than one Hardcover book; those are skipped).
- [ ] Apply: re-run with `--apply`. It's resumable and only touches rows where `hardcover_book_id IS NULL`. It makes about 1 request per 100 spines at 1.2 s apart, within the 60-per-minute limit.
- [ ] Revoke or delete the PAT afterwards, and clear the exported variables.

## Part G: Frontend work (not in this repo)

The backend contract is in section 10 of `plans/02-hardcover-oauth.md`. Short version:

- [ ] A **`/oauth/callback` route**: compare the `state` in the URL with the one stored in `sessionStorage` **before** calling the backend (blocks login-CSRF), then `POST /auth/hardcover/callback {code, state, iss}`. Store `username` and `authtoken` the same way as password login.
- [ ] A **"Sign in with Hardcover"** button: `POST /auth/hardcover/start {mode: "login"}`, store the returned `state`, then redirect to `authorize_url`. Remove the register tab; keep the password form for legacy users.
- [ ] A **"Link Hardcover"** button in the profile: `POST /auth/hardcover/start {mode: "link", username, authtoken}`.
- [ ] A **shelf picker and generation** using `/hardcover/shelves` and `/hardcover/shelf`.
- [ ] Handle `401 hardcover_reauth_required` by re-running the start flow; the site session is still valid.
- [ ] Handle `409 hardcover_already_linked` and `409 account_linked_to_different_hardcover`.
- [ ] Message for legacy users on the sign-in page: log in with your password first, then link Hardcover from your profile. Otherwise a legacy user who clicks "Sign in with Hardcover" gets a second, empty account.
- [ ] Uploading a spine for a book with only a Hardcover ID must send `hardcover_book_id` (and no `book_id`).
- [ ] Rating display: Hardcover's `3.5` is returned as the string `"4"` (rounded half up). Check that matches what you want.

## Behaviour changes worth a second look (from the implementation report)

1. **Shared DAO behaviour:** after a swallowed database error, `exec_statement` and `exec_statement_fetch` now call `conn.rollback()`. Before, one failed insert left the connection aborted and broke every later query in that Lambda container. This affects **all** lambdas.
2. **Banned users** are now cut off mid-session in every lambda, not only at login.
3. **Session lifetime** is 30 days. `get_7_days_from_now` remains as an alias for `get_session_expiry()`, which now returns an **int** (it used to return a string). The column is `INT`, so this is compatible.
4. **Any failed token refresh** marks the connection as needing re-authorisation, including timeouts and Hardcover 5xx or 429 replies, because a retry could be a replay that revokes the whole chain. A short Hardcover outage during a refresh can force users to reconnect.
5. **Logout** revokes the Hardcover refresh token. A legacy user who linked Hardcover and then logs out will have to reconnect before building Hardcover shelves again. A failed revoke leaves the tokens valid on Hardcover until they expire.
6. **One session per user:** an OAuth login replaces the previous session, signing the user out of other devices. This matches the existing password behaviour.
7. **The refresh holds a database row lock** while it calls Hardcover (15 s timeout). A slow Hardcover can block that user's other concurrent requests.
8. **Hardcover username characters** are sanitised to `[A-Za-z0-9_.-]`, max 50 characters. Only one real username sample (15 lowercase letters) has been seen.
9. **Discovered OAuth URLs** are accepted only on Hardcover's own hosts, so a bad discovery document can't redirect the client secret elsewhere.
10. **Existing spines** don't match Hardcover books by ID until the backfill runs.

## Known gaps

- `sam build` has not been run (`sam validate` passed; see Part B).
- Users who sign in without `offline_access` get a refresh token, but the spike did not retest refreshing it, so its lifetime may differ.
- `mint_session` and the update paths surface database failures only as 500s, with no detail logged, because `exec_statement` swallows errors.
- Account merging, unlinking and email-based recovery are out of scope, as the plan states.
- Pagination is capped at 40 pages of 500 books (20,000 books).
