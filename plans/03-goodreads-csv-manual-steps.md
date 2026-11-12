# Goodreads CSV Import: Manual Steps Remaining

The code for Plan 1 is committed (`68b5a0b`) and pushed to `origin/BRIO-35596`. Everything below is work only you can do: AWS changes, checks against production data, and decisions about deployment. Items are in suggested order. Anything marked **(if needed)** depends on what already exists in your AWS account, which I can't see.

## 0. Know what you're deploying

| Item | State in the repo | What production needs |
|---|---|---|
| `importGRLibraryCsv` Lambda (`lambdas/import_gr_library_csv/`) | Code done, tested, `MemorySize: 512` in `infra/template.yaml` | A new function, plus an API route `POST /importgrlibrary` |
| `getGRBookshelf` Lambda (`lambdas/get_gr_bookshelf/`) | Now just returns HTTP 410 with a message | Redeploy the new code so the dead RSS path says why it fails |
| Shared layer (`src/`) | `feedparser` removed from the code and requirements | A rebuilt layer version, attached to both functions |

Nothing deploys from this repo yet. `docs/TODO-setup-aws-deploy.md` says production lambdas are zipped and uploaded by hand, `make deploy` has no stack name, and the CI `deploy` job has no AWS credentials. Decide first (Step 1) whether you finish the SAM stack or deploy by hand.

## 1. Choose how to deploy

**Option A: by hand, like the existing lambdas.** Fastest. Steps 2 to 5 below describe it.

**Option B: finish the SAM stack** (checklist in `docs/TODO-setup-aws-deploy.md`: parameters, a name prefix, `sam deploy --guided`, API URL decision). Better long term, but it is a separate project and changes the API URL the frontend uses.

The rest of this file assumes Option A. If you pick B, Steps 2 to 4 become part of that stack work.

## 2. Check for the one thing that can leak private data

The uploaded CSV contains the user's private reviews and notes, and it travels in the request body.

- [ ] In API Gateway, open the stage that serves the API (the current one is `alpha`) → Logs/Tracing. Confirm **"Log full requests/responses data" is OFF** and that CloudWatch execution logging is not set to `INFO` with data tracing. If it is on, every uploaded CSV, including reviews, lands in CloudWatch.
- [ ] Check there's no WAF rule, access-log format or X-Ray setting that records request bodies.
- [ ] Confirm the Lambda's own logging stays to counts only. The handler already prints only `looking for N books`, so no change needed.

## 3. Deploy the Lambdas

### 3a. Build the layer without `feedparser`

From the repo root (needs Docker running; the Makefile expects the Colima socket):

```
make layer-deps
```

`layer-deps` installs Linux-compiled packages into `src/`. Then zip the layer contents so they sit under a `python/` folder, which is what Lambda layers require. Check how your existing layer is laid out before choosing the zip root. In the AWS console, publish a **new layer version** and note its ARN. (Don't delete the old version yet; the old functions still use it.)

### 3b. Create or update `importGRLibraryCsv` **(if needed)**

1. Package the handler: the function code is `lambdas/import_gr_library_csv/handler.py`, and it imports `bookshelf.*` from the layer. The layer must therefore include `src/bookshelf/`. Confirm that your layer contains the new `gr_csv.py`, `http.py` and the updated `bookshelf.py`.
2. Create the function (Python 3.12, handler `handler.lambda_handler`), or update the existing one.
3. Settings: **memory 512 MB**, timeout 30 s, attach the new layer version.
4. Environment variables, matching your other functions:
   - `DATABASE_URL`: the same Cockroach connection string the other lambdas use
   - `CERT_SECRET_ARN`: the same value the others use
   - `SKIP_SSL_CERT`: leave **unset** in production
5. Execution role: it needs `secretsmanager:GetSecretValue` on the cert secret (copy the role or policy from a working function such as `loginRegister`) plus basic CloudWatch Logs access.

### 3c. Update `getGRBookshelf`

Upload the new handler (`lambdas/get_gr_bookshelf/handler.py`) and attach the new layer version. After this it returns `410 {"error": "Goodreads RSS is no longer available. Upload your Goodreads export instead."}`.

### 3d. Add the API route

In API Gateway, on the same API the frontend already calls:

- [ ] Create resource `/importgrlibrary` with method `POST`.
- [ ] Integration: **Lambda proxy integration**. The new handlers return `{"statusCode", "body", "headers"}` and read `event["body"]` as a JSON string. Older functions in this API use non-proxy mappings that send flat events, so don't copy their integration settings.
- [ ] Enable CORS for the resource: allow `POST` and `OPTIONS`, header `Content-Type`, and your site's origin. The handler also sets `Access-Control-Allow-Origin: *` on responses; an `OPTIONS` preflight still needs a method on the resource.
- [ ] Add Lambda invoke permission for the API on the function (the console prompts for it).
- [ ] **Deploy the API** to the stage. API Gateway changes do nothing until you deploy them to a stage.
- [ ] Payload limits to know: API Gateway accepts up to 10 MB; Lambda accepts 6 MB. The handler rejects anything over 4,000,000 characters with HTTP 413 and a message, but a very large non-ASCII file could hit Lambda's own 6 MB limit first and return a generic error. The frontend should also refuse files over about 3 MB before uploading.

## 4. Smoke test against the deployed endpoint

Replace `API` with your stage URL. Keep the export file out of the repo.

```
API=https://<api-id>.execute-api.us-east-1.amazonaws.com/<stage>
EXPORT=~/Downloads/goodreads_library_export.csv

# 1. list shelves (builds the JSON body from the file safely, newlines and quotes included)
jq -Rs '{csv: .}' "$EXPORT" | curl -s -X POST "$API/importgrlibrary" -H 'Content-Type: application/json' -d @- | jq '.body | .shelves[:5]'

# 2. one shelf
jq -Rs --arg s read '{csv: ., shelf: $s}' "$EXPORT" | curl -s -X POST "$API/importgrlibrary" -H 'Content-Type: application/json' -d @- | jq '{status: .statusCode, found: (.body.found | length), unfound: (.body.unfound | length)}'

# 3. unknown shelf should be a 404
jq -Rs --arg s nope '{csv: ., shelf: $s}' "$EXPORT" | curl -s -i -X POST "$API/importgrlibrary" -H 'Content-Type: application/json' -d @- | head -1

# 4. bad body should be a 400
curl -s -i -X POST "$API/importgrlibrary" -H 'Content-Type: application/json' -d 'not json' | head -1

# 5. the old endpoint should now say 410
curl -s -i "$API/getgrbookshelf?userid=1&shelfname=read" | head -1
```

Then check:
- [ ] `read` returns roughly 741 books across `found` plus `unfound`, in a reasonable time. **Note the response time**; this is the performance check from Plan 1 §4.6, which was not done. If the `read` shelf takes more than a few seconds, the matching query needs chunking (about 200 books per query).
- [ ] The response for `read` stays under 6 MB. If it ever doesn't, Lambda returns an error; the shelf-at-a-time design is what keeps this safe.
- [ ] CloudWatch for `importGRLibraryCsv` shows only counts, with no titles, reviews or notes.

## 5. Check production spine titles (Plan 1 §4.4)

The title-suffix question was verified only on the seed data. On production, look at whether stored titles keep the series suffix like `(Series, #1)`. Run in the Cockroach SQL shell:

```sql
SELECT count(*) AS total,
       count(*) FILTER (WHERE title ~ '\(.*#\s*\d') AS with_series_suffix
FROM bookshelf;
```

- If most titles include the suffix, exact title matching against the CSV already works. Nothing to do.
- If almost none do, tell me and I'll add the suffix-stripped matching variant described in the plan.

## 6. Frontend changes this depends on (not in this repo)

The backend contract changed, so the frontend in `~/projects/bookshelf-ts-site` needs matching changes. This is outside the scope of the backend work, but nothing will work end-to-end without it:

- [ ] A file picker that reads the CSV and calls `POST /importgrlibrary` with `{csv}` to list shelves, then `{csv, shelf}` for the chosen shelf.
- [ ] Handle the new responses: **413** (file too large, show a message), **404** (shelf not in this export), **400** (not a Goodreads export or bad request), and **410** from the old `getgrbookshelf` route.
- [ ] Refuse files over about 3 MB before uploading.
- [ ] Remove the dead "Goodreads user ID" flow for CSV imports: there is no Goodreads user ID in the file, and `gr_user_id` / `goodreads_id` don't apply to this path.
- [ ] Point `REACT_APP_API_URL` at the API you deployed to if it changed.

## 7. Before merging to `master`

- [ ] **Fix or remove the CI `deploy` job** in `.github/workflows/ci.yml`. It runs `make deploy` on every push to `master`, has no AWS credentials, and will fail, as `docs/TODO-setup-aws-deploy.md` warns.
- [ ] Open the PR. The skill that creates BRIO commit messages needs the ticket type for BRIO-35596 (story or bug), which I couldn't look up; use `feat:` for a story and `fix:` for a bug.
- [ ] The branch also contains the whole `refactor` branch from the earlier merge. Check the PR diff is what you expect.

## 8. Cleanup, whenever convenient (not blocking)

- [ ] Delete the `get_books_from_shelf` leftovers: the legacy copies in `aws_lambdas/python/` (`getGRbookshelf_lambda.py`, `bookshelf.py`) still import `feedparser`, and `feedparser` / `sgmllib` are still vendored there.
- [ ] Remove the `getGRBookshelf` route entirely once the frontend no longer calls it, instead of leaving a 410.
- [ ] The repo has about 140 pre-existing `ruff` errors (mostly import order). The Plan 1 files are clean.
- [ ] If real users hit the 4 MB limit, build the S3 upload path left as a `TODO` in `lambdas/import_gr_library_csv/handler.py`. It needs a privacy review first, since stored exports contain private reviews.
