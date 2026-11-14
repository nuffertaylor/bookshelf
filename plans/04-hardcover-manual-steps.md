# Hardcover OAuth: Manual Steps Remaining

Status as of 2026-11-14: the code is written, committed and tested on the `hardcover_integration` branch of both repos (`bookshelf` for the backend, `bookshelf-ts-site` for the frontend), and both merge cleanly into `master`. It has been run against the real Hardcover API from a local machine (a shelf load worked), but **nothing from this work is deployed or has touched production yet**. What's left is work only you can do: local verification of the remaining cases, AWS resources, the production database migration, the backfill, and the merges.

**Windows:** each command block below is followed by a PowerShell version. Run them from the repo root (`bookshelf`) in PowerShell, not Command Prompt. Install what's missing with `winget`, for example `winget install -e --id astral-sh.uv` for `uv`, and `winget install -e --id Amazon.AWSCLI` and `winget install -e --id Amazon.SAM-CLI` as in `docs/deploy.md`. After installing anything, quit and reopen your terminal (VS Code included) so it's on the PATH. Keep real secrets out of any file git tracks, and note that anything you type into PowerShell is kept in its history (`Get-History`, and the file at `(Get-PSReadLineOption).HistorySavePath`).

## Before merging into master: checklist

Order matters. **Merging the backend into `master` deploys it immediately** (GitHub Actions), so everything the deploy depends on must exist first. The frontend merges last.

1. [ ] **Try the remaining cases locally against real Hardcover** (Part B). At minimum: sign in with Hardcover, sign out and back in (same account), link Hardcover from a password account, load a **custom list** (that query has never run against the real API), and revoke the app then load a shelf (expect a "reconnect" prompt).
2. [ ] **Create the AWS resources** (Part C): the KMS key, the Hardcover client secret in Secrets Manager, and three SSM parameters. The deploy fails if the parameters are missing (the running site is unaffected, but the deploy is blocked).
3. [ ] **Check the Hardcover app settings** (Part C): `https://www.mybookshelf.dev/oauth/callback` must be registered exactly, since the deploy hardcodes it. Confirm that is your real production address.
4. [ ] **Back up, then migrate the production database** (Part D). It's safe to run before the deploy: the code that's live now keeps working against the migrated database (verified, see Part D).
5. [ ] **Merge the backend `hardcover_integration` into `master`** and watch the **CI** run in the Actions tab (Part E). Then smoke test the new API.
6. [ ] **Run the backfill** (Part F) once the migration is in. Do it before the frontend goes live, so series books match by ID from day one.
7. [ ] **Merge the frontend `hardcover_integration` into `master`**. Vercel deploys it (Part G). Then test sign-in, link and a Hardcover list on the live site.
8. [ ] **Clean up**: revoke the Hardcover personal access token, delete any local secret files, and clear exported variables.

## Part A: Code status

Done, so nothing to do here. For reference:

- Backend: branch `hardcover_integration` in `bookshelf`. Frontend: branch `hardcover_integration` in `bookshelf-ts-site`.
- Tests: 193 pass with a local Postgres running (183 without it, since the real-database tests skip). The token-refresh concurrency test, the one that proves two simultaneous refreshes spend the refresh token only once, **passes on Postgres 15 and on a local CockroachDB v22.1.8**. (It was failing before because its test data put a too-large number in a 32-bit Postgres column. That's a test-data fix, not a product bug.)
- The title/author matching change (series suffixes, quotes, spacing) is verified against both databases, needs no migration, and ships with the backend.
- Skim "Behaviour changes" at the end before merging; item 1 changes shared database behaviour for **every** lambda.

## Part B: Verify locally before touching AWS

These need Docker running (your Makefile expects the Colima socket on macOS; Docker Desktop on Windows).

- [ ] **Re-run the row-lock test on your machine:**
  ```
  make dev
  uv run pytest tests/integration -rs
  ```
  PowerShell (there is no `make` on Windows; `make dev` only starts the containers):
  ```powershell
  docker compose -f local-dev/docker-compose.yml up -d
  uv run pytest tests/integration -rs
  ```
  It must pass, not skip. It checks that two simultaneous token refreshes spend the refresh token exactly once. If it fails, stop: a double-spend revokes the user's whole Hardcover connection.
- [ ] **Start LocalStack with KMS.** `docker-compose.yml` now sets `SERVICES: s3,kms`, so recreate the container (`docker compose -f local-dev/docker-compose.yml up -d --force-recreate localstack`). Then create a local key:
  ```
  aws --endpoint-url http://localhost:4566 --region us-east-1 kms create-key
  ```
  Note the `KeyId` in the output. (LocalStack accepts dummy credentials such as `test`/`test`.)

  PowerShell. The dummy credentials apply to this window only and keep your real AWS keys out of it:
  ```powershell
  docker compose -f local-dev/docker-compose.yml up -d --force-recreate localstack
  $env:AWS_ACCESS_KEY_ID="test"; $env:AWS_SECRET_ACCESS_KEY="test"; $env:AWS_DEFAULT_REGION="us-east-1"
  $kms = aws --endpoint-url http://localhost:4566 kms create-key --query KeyMetadata.KeyId --output text
  $kms
  ```
  `$kms` holds the key ID for the next step, so keep using the same window.
- [ ] **Apply the migration to your local database** if it was created before this change (a fresh `make dev` already loads `migrate.sql`):
  ```
  psql postgresql://postgres:dev@localhost:5432/bookshelf -f local-dev/migrations/001_hardcover_oauth.sql
  ```
  PowerShell (runs `psql` inside the Postgres container, so nothing else needs installing):
  ```powershell
  Get-Content local-dev\migrations\001_hardcover_oauth.sql -Raw | docker compose -f local-dev/docker-compose.yml exec -T postgres psql -U postgres -d bookshelf
  ```
  Without this, shelf lookups quietly return nothing, because the matching query refers to a column that doesn't exist yet and the database layer swallows the error.
- [ ] **Run the whole stack with real Hardcover.** In the terminal where you run `make local`:
  ```
  export KMS_KEY_ID=<KeyId from above>
  export HARDCOVER_CLIENT_ID=a062038b-5d7e-4646-ace2-e250b8457cc4
  export HARDCOVER_CLIENT_SECRET=[YOUR-CLIENT-SECRET]
  make local
  ```
  Leave out the brackets when you type the secret. The command is not echoed by `make`, but the secret **is visible in the process arguments** on your machine while SAM runs. That's acceptable on a personal laptop; don't do it on a shared one.

  PowerShell (`make local` isn't available; these are its steps). Use the same window as the key step, so `$kms` is still set:
  ```powershell
  $env:HARDCOVER_CLIENT_SECRET="<your client secret>"
  sam build --template infra/template.yaml
  robocopy src .aws-sam\build\BookshelfLayer\python /E /XD .aws-sam __pycache__
  sam local start-api --port 3001 --parameter-overrides `
    AwsEndpointUrl="http://host.docker.internal:4566" `
    KmsEndpointUrl="http://host.docker.internal:4566" `
    KmsKeyId=$kms `
    HardcoverClientId="a062038b-5d7e-4646-ace2-e250b8457cc4" `
    HardcoverClientSecret=$env:HARDCOVER_CLIENT_SECRET
  ```
  Robocopy exit codes 1 to 7 mean success. Run `robocopy` again after every `sam build`, because a rebuild wipes the copied files. If you have never installed the Linux Python packages into `src/`, do step 5 of `docs/windows-setup.md` first. Do not use `--use-container` here. The same caveat about the secret being visible in the process arguments applies. Then run the frontend in a second window with `npm start`.
- [ ] **Run the frontend on port 3000** (`bookshelf-ts-site`, branch `hardcover_integration`; its `.env.development` already points at port 3001) and walk through: sign in, new account created; sign out and in again, same account; link from a legacy (password) account and confirm the Profile shows Hardcover as connected after a later password login; build a Hardcover shelf.
- [ ] **Test the cases the mocks can't prove:**
  1. **Revoked app:** revoke the app at `hardcover.app/account/api/authorized-apps`, then request a shelf. Expect HTTP 401 `hardcover_reauth_required`, the site session still valid, and the "Connect Hardcover" prompt in the Create tab. The code can't detect a Hardcover reply of HTTP 200 that contains an auth error; confirm what Hardcover actually returns.
  2. **List shelves:** the query for books inside a custom list is marked `TODO(live)` in `src/bookshelf/hardcover_library.py` because it was never tested with variables. Request a list shelf and check the result. This is the case most likely to need a fix.
  3. **Large shelf:** your `Read` shelf has about 740 books (2 to 3 pages). Check time and rate-limit headers.
  4. **Username clash:** make a legacy account whose username matches a Hardcover username and confirm the new Hardcover account gets `-2`.
  5. **Link conflicts:** try to link one Hardcover account to two bookshelf accounts; expect 409 `hardcover_already_linked`.
  6. **Banned:** set `banned` on a test user and confirm password login and an existing session are both refused.
  7. **Logout keeps the link:** log out and back in with a password; building a Hardcover shelf should not ask to connect again.
- [x] **Template validation (done):** `sam validate --lint --template infra/template.yaml` passes with no findings.
- [ ] **Optional:** `sam build --template infra/template.yaml` locally. The CI deploy runs the container build on merge, which is the one that matters.
  PowerShell: the same command works. For a build that matches deployment, use the container build from `docs/deploy.md` (step 3), which avoids Windows dropping compiled `.so` files from the layer.

## Part C: AWS resources (production)

I have not created or changed anything in AWS. Replace placeholders in brackets (without the brackets). Use your normal profile, in the **same account and region (us-east-1) as the `bookshelf` stack**.

- [ ] **KMS key** for encrypting stored tokens:
  ```
  aws kms create-key --description bookshelf-hardcover-tokens
  aws ssm put-parameter --name /bookshelf/kms_key_id --type String --value [KeyId]
  ```
  PowerShell:
  ```powershell
  $key = aws kms create-key --description bookshelf-hardcover-tokens --query KeyMetadata.KeyId --output text
  aws ssm put-parameter --name /bookshelf/kms_key_id --type String --value $key
  ```
- [ ] **Client secret** in Secrets Manager. Enter it from a file or an interactive prompt that is not tracked by git, never inline in a shared shell history:
  ```
  aws secretsmanager create-secret --name bookshelf/hardcover-client-secret --secret-string file://[path-to-untracked-file]
  aws ssm put-parameter --name /bookshelf/hardcover_secret_arn --type String --value [secret ARN]
  aws ssm put-parameter --name /bookshelf/hardcover_client_id --type String --value a062038b-5d7e-4646-ace2-e250b8457cc4
  ```
  Delete the local file afterwards.

  PowerShell. Create `secret.txt` in an untracked location with Notepad, containing only the secret and no trailing blank line, then:
  ```powershell
  $arn = aws secretsmanager create-secret --name bookshelf/hardcover-client-secret --secret-string file://C:\path\to\secret.txt --query ARN --output text
  aws ssm put-parameter --name /bookshelf/hardcover_secret_arn --type String --value $arn
  aws ssm put-parameter --name /bookshelf/hardcover_client_id --type String --value a062038b-5d7e-4646-ace2-e250b8457cc4
  Remove-Item C:\path\to\secret.txt
  ```
  Use the real path in both places (keep the `file://` prefix and backslashes).
- [ ] **Confirm the existing parameters are still there:** `/bookshelf/database_url` and `/bookshelf/cert_secret_arn` (from the first deploy). The deploy needs all five.
  ```
  aws ssm get-parameters-by-path --path /bookshelf --query "Parameters[].Name" --output text
  ```
  PowerShell: the same command works. You should see five names.
- [ ] **IAM:** the template creates the shared `HardcoverAccessPolicy`, which grants KMS `Encrypt`/`Decrypt` on that one key and `GetSecretValue` on that one secret. It is attached to **three** functions: `hardcoverAuthCallback`, `getHardcoverShelves` and `getHardcoverShelf`. `hardcoverAuthStart` and `logout` need neither. The GitHub deploy role needs nothing new: it can already read `/bookshelf/*` parameters and create `bookshelf-*` roles and policies. That is expected from how the role is written, but it is untested until the first real deploy, so if the deploy fails on a permission, the CI log names it.
- [ ] **Hardcover app settings:** confirm `https://www.mybookshelf.dev/oauth/callback` and `http://localhost:3000/oauth/callback` are both registered. Both already are, per the earlier setup. The production one must match the address your site is really served from, because `make deploy` passes exactly that value.

## Part D: Production database migration

Do this **before** the backend merge, and take a backup or snapshot first.

**Compatibility (verified):** the migration is backwards compatible. I ran the code that is live today (`master`) against a database built from the original table definitions, applied this migration, and compared. All nine read methods returned identical results, the live write methods still worked afterwards (the new `hardcover_book_id` column just stays empty on those rows), and there were no SQL errors, on PostgreSQL 15 and CockroachDB v22.1.8. The migration is also safe to re-run (applied three times in a row on both). So running it early doesn't break the site. Two limits: this used table definitions from the code, not your actual production tables (hence the column-order check below), and after Hardcover code is live, rolling back is not clean, because accounts with no password and spines with no Goodreads ID will exist, and the `NOT NULL` rules can't be restored once they do.

- [ ] Back up or snapshot the CockroachDB cluster (or at least the `bookshelf`, `unfound_to_upload` and `bookshelf_users` tables).
- [ ] Run each statement in `local-dev/migrations/001_hardcover_oauth.sql` **one at a time, outside an explicit transaction**, in the Cockroach SQL shell. CockroachDB limits schema changes inside transactions. Every statement is safe to re-run.

  The simplest way on any OS is to open the cluster's **SQL Shell in the CockroachDB Cloud console** and paste the statements one at a time. From PowerShell, if you have `psql` or the `cockroach` CLI, use your production connection string (with `sslmode=verify-full`) and your `root.crt`:
  ```powershell
  $env:DATABASE_URL = "<the production connection string>"
  $env:PGSSLROOTCERT = "$PWD\root.crt"
  psql $env:DATABASE_URL -v ON_ERROR_STOP=1 -f local-dev\migrations\001_hardcover_oauth.sql
  ```
  `psql -f` sends the statements one by one and does not wrap them in a transaction, which is what this migration needs. It stops at the first error. I haven't run this against your cluster, so if anything looks off, switch to pasting the statements in the SQL shell. When done: `Remove-Item Env:DATABASE_URL`. Never paste the connection string into chat or a tracked file; it contains the database password.
- [ ] Verify that the DAO's position-based column mapping still holds. `SELECT * FROM bookshelf LIMIT 1;` must show `hardcover_book_id` as the **last** column (index 15), and `SELECT * FROM unfound_to_upload LIMIT 1;` must show it at index 10. If the order differs, stop and tell me; the DAO would silently misread rows.

  PowerShell (uses the `DATABASE_URL` and `PGSSLROOTCERT` from the previous step):
  ```powershell
  psql $env:DATABASE_URL -Atc "SELECT column_name FROM information_schema.columns WHERE table_name='bookshelf' ORDER BY ordinal_position"
  psql $env:DATABASE_URL -Atc "SELECT column_name FROM information_schema.columns WHERE table_name='unfound_to_upload' ORDER BY ordinal_position"
  ```
  The last line printed for each command must be `hardcover_book_id`.
- [ ] Verify existing logins still work: sign in with a legacy account before and after the migration.

## Part E: Deploy

Deploys now run automatically. Pushing to `master` runs the **CI** workflow (`.github/workflows/ci.yml`): the tests first, then the `deploy` job, which assumes an AWS role through OIDC and runs `make deploy`. There is no manual zip-and-upload route anymore. `docs/deploy.md` has the one-time setup and troubleshooting, and that setup is already done.

What the first deploy of this work does:
- It creates the five Hardcover functions and the shared `HardcoverAccessPolicy`, and updates the existing functions with the new layer. Functions are named with the stack's prefix, so they appear as `v2-hardcoverAuthStart` and so on.
- `make deploy` passes the Hardcover values from the SSM parameters from Part C, plus the production redirect URI. **If any parameter is missing, CloudFormation can't resolve it and the deploy fails.** The running site stays on its current version.
- Environment variables, routes and CORS come from `infra/template.yaml`. Nothing to configure by hand.
- Only the new API gets the Hardcover routes. The old `/alpha/` API keeps its old code.

New or changed functions and routes:

| Function | Route | Notes |
|---|---|---|
| `hardcoverAuthStart` | `POST /auth/hardcover/start` | no secret needed |
| `hardcoverAuthCallback` | `POST /auth/hardcover/callback` | needs secret and KMS |
| `logout` | `POST /logout` | ends the site session; Hardcover stays linked |
| `getHardcoverShelves` | `POST /hardcover/shelves` | needs secret and KMS; timeout 60 s |
| `getHardcoverShelf` | `POST /hardcover/shelf` | needs secret and KMS; timeout 60 s, 512 MB |
| `loginRegister`, `uploadSpine`, `addUnfoundToUpload` | existing routes | updated code (`loginRegister` now also reports the Hardcover link) |

- [ ] Merge the backend `hardcover_integration` into `master`, then open the Actions tab and watch **CI** (`test`, then `deploy`). If `deploy` fails, send me the failing step's log.
- [ ] **Smoke test the new API** (the URL is the `ApiUrl` stack output, with its trailing slash). This one call also writes a row to `oauth_states`, which expires on its own:
  ```
  curl -X POST "<ApiUrl>auth/hardcover/start" -H "Content-Type: application/json" -d '{"mode":"login"}'
  ```
  PowerShell:
  ```powershell
  Invoke-RestMethod -Method Post -Uri "<ApiUrl>auth/hardcover/start" -ContentType "application/json" -Body '{"mode":"login"}'
  ```
  The response should contain an `authorize_url` and a `state`. A 500 with "not configured" means a Hardcover environment variable didn't reach the function.
- [ ] Check the API Gateway stage does **not** log full request/response bodies: these requests carry authorization codes and session tokens. (API Gateway console, the `Prod` stage, Logs/Tracing.)

## Part F: Backfill existing spines

Without this, existing community spines match Hardcover books only by normalized title and author, so a book whose Hardcover title differs from the Goodreads one (a subtitle, another edition) still shows as missing. With it, every old spine that Hardcover can map gets its Hardcover book ID and matches exactly.

- [ ] Create a Hardcover **personal access token** with the `read:catalog` scope, from `hardcover.app/account/api`. It reads catalog data, not anyone's private library. I haven't confirmed that page lets you choose scopes; if the dry run reports `insufficient_scope`, the token lacks it, and we'd get one another way.
- [ ] Dry run first (writes nothing):
  ```
  export DATABASE_URL=[connection string]
  export HARDCOVER_TOKEN=[the PAT]
  uv run python local-dev/scripts/backfill_hardcover_ids.py
  ```
  For production CockroachDB add `--sslrootcert [path to ca.crt]`.

  PowerShell:
  ```powershell
  $env:DATABASE_URL = "<the production connection string>"
  $env:HARDCOVER_TOKEN = "<the PAT>"
  uv run python local-dev\scripts\backfill_hardcover_ids.py --sslrootcert .\root.crt
  ```
- [ ] Read the dry-run summary (how many spines map, how many don't, how many Goodreads IDs map to more than one Hardcover book; those are skipped).
- [ ] Apply: re-run with `--apply`. It's resumable and only touches rows where `hardcover_book_id IS NULL`. It makes about 1 request per 100 spines at 1.2 s apart, within the 60-per-minute limit.

  PowerShell: `uv run python local-dev\scripts\backfill_hardcover_ids.py --sslrootcert .\root.crt --apply`
- [ ] Revoke or delete the PAT afterwards, and clear the exported variables.

  PowerShell: `Remove-Item Env:DATABASE_URL, Env:HARDCOVER_TOKEN`

## Part G: Frontend

The frontend work is built and pushed on the `hardcover_integration` branch of `bookshelf-ts-site`. Contract details are in section 10 of `plans/02-hardcover-oauth.md`. What it does:

- A `/oauth/callback` page that checks the `state` against `sessionStorage` before calling the backend, then stores the session like a password login.
- "Sign in with Hardcover" on the Login tab (the Register tab is removed), with a note for existing users to log in with their password first and link Hardcover from the profile.
- "Link Hardcover" on the Profile, which now also shows an existing link after a password login.
- A "Hardcover" tab on Create with a list picker, handling "reconnect Hardcover" (401), session expiry, rate limits, and the two 409 conflicts.
- Uploading a spine for a book that only has a Hardcover ID sends `hardcover_book_id` and no `book_id`.
- A `vercel.json` rewrite so `/oauth/callback` loads the app, a How To entry, and a server-side logout.

Still to do:

- [ ] **Merge the frontend after the backend is deployed**, because the new buttons call routes that only exist after the backend deploy. Check in Vercel that its Production Branch is `master` (it was for the last release); the `REACT_APP_API_URL` and `REACT_APP_IMG_URL_PREFIX` variables are already set.
- [ ] Test on the live site: sign in with Hardcover, link from a password account, load a list, and check that returning to the site after Hardcover lands in the app (not a 404).
- [ ] Rating display: Hardcover's `3.5` is returned as the string `"4"` (rounded half up). Check that matches what you want.

## Behaviour changes worth a second look (from the implementation report)

1. **Shared DAO behaviour:** after a swallowed database error, `exec_statement` and `exec_statement_fetch` now call `conn.rollback()`. Before, one failed insert left the connection aborted and broke every later query in that Lambda container. This affects **all** lambdas.
2. **Banned users** are now cut off mid-session in every lambda, not only at login.
3. **Session lifetime** is 30 days. `get_7_days_from_now` remains as an alias for `get_session_expiry()`, which now returns an **int** (it used to return a string). The column is `INT`, so this is compatible.
4. **Any failed token refresh** marks the connection as needing re-authorisation, including timeouts and Hardcover 5xx or 429 replies, because a retry could be a replay that revokes the whole chain. A short Hardcover outage during a refresh can force users to reconnect.
5. **Logout keeps Hardcover linked.** Linking is a one-time step, so logging out only ends the site session; the stored Hardcover tokens are neither revoked nor marked for re-authorisation. Password login also reports the existing link (`hardcover_username`, `hardcover_needs_reauth`) so the frontend doesn't ask users to link again. To disconnect, users revoke My Bookshelf in their Hardcover account's authorized apps.
6. **One session per user:** an OAuth login replaces the previous session, signing the user out of other devices. This matches the existing password behaviour.
7. **The refresh holds a database row lock** while it calls Hardcover (15 s timeout). A slow Hardcover can block that user's other concurrent requests.
8. **Hardcover username characters** are sanitised to `[A-Za-z0-9_.-]`, max 50 characters. Only one real username sample (15 lowercase letters) has been seen.
9. **Discovered OAuth URLs** are accepted only on Hardcover's own hosts, so a bad discovery document can't redirect the client secret elsewhere.
10. **Existing spines** don't match Hardcover books by ID until the backfill runs. Until then they match by title and author.
11. **Title and author matching is looser** for every shelf, Goodreads included: case, repeated spaces, curly versus straight quotes and a trailing `(Series, #n)` are ignored when comparing (`src/bookshelf/text_match.py`). Everything that matched before still matches. When several spines match a book, they are now returned oldest upload first, so a shelf opens with the same edition every time. Stored and displayed titles are unchanged.

## Known gaps

- Custom Hardcover lists (`list_books`) have never been exercised against the real API (the `TODO(live)` in `hardcover_library.py`). Test one in Part B before relying on it.
- Production hasn't been exercised at all: the real CockroachDB cluster, the real KMS key and secret, and the deployed lambdas. The database checks above used local Postgres 15 and a local CockroachDB v22.1.8 (your cluster may run a newer version).
- Users who sign in without `offline_access` get a refresh token, but the spike did not retest refreshing it, so its lifetime may differ.
- `mint_session` and the update paths surface database failures only as 500s, with no detail logged, because `exec_statement` swallows errors. That is also why a missing database column shows up as "no results" rather than an error.
- Initials in author names are not normalised (`N. K. Jemisin` does not match `N.K. Jemisin` by title and author).
- Rolling back after Hardcover accounts exist is not clean (see Part D).
- Account merging, unlinking and email-based recovery are out of scope, as the plan states.
- Pagination is capped at 40 pages of 500 books (20,000 books).
