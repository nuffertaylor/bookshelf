# Bookshelf Refactor Plan

## Goals
- Add testing infrastructure
- Simplify deployments (replace manual zip + AWS CLI comments with SAM)
- Enable local development without hitting AWS
- Make the codebase approachable for open-source contributors

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Deployment tool | AWS SAM | Free, AWS-native, enables `sam local` simulation, one-command deploys |
| Shared code packaging | Lambda Layer | Single layer for `src/bookshelf`, smaller per-function zips, no version drift |
| Database | CockroachDB only | DynamoDB is fully legacy; removing `dynamodb_dao.py` and `getSpineLambda.py` |
| Python version | 3.12 | 3.8 is past Lambda end-of-life (Feb 2024); `sam build --use-container` handles psycopg2 recompilation |
| SSL cert (root.crt) | AWS Secrets Manager | Keeps cert out of version control; fetched at runtime in `CockroachDAO.__init__` |
| S3 bucket / shelf config | Leave hardcoded | Not expected to vary across contributors |

---

## Target Project Structure

```
bookshelf/
├── lambdas/
│   ├── login_register/
│   │   └── handler.py
│   ├── upload_spine/
│   │   └── handler.py
│   ├── gen_shelf/
│   │   └── handler.py
│   └── ... (one dir per active lambda)
├── src/
│   └── bookshelf/
│       ├── __init__.py
│       ├── dao/
│       │   ├── cockroachdb_dao.py
│       │   └── s3_dao.py
│       ├── bookshelf.py      (shelf image generation core)
│       ├── auth.py           (hash/salt, token validation helpers)
│       └── http.py           (shared httpResult helper)
├── tests/
│   ├── unit/
│   └── integration/
├── infra/
│   └── template.yaml         (AWS SAM)
├── local-dev/
│   └── docker-compose.yml
├── example/                  (keep — LeagueGothic.ttf used by shelf generator)
├── pyproject.toml
├── Makefile
├── .env.example
└── README.md
```

---

## Phases

### Phase 1 — Cleanup & Dependency Management
- Delete legacy top-level files: `bookshelf.py`, `get_books.py`, `myBooks.py`, `nextread.py`, `randCol.py`, `get_books_lambda.py`, `bookshelf_stats.py`
- Delete unused lambda + DAO: `aws_lambdas/python/dynamodb_dao.py`, `aws_lambdas/python/getSpineLambda.py`
- Remove vendored third-party code: `feedparser/`, `colorthief.py`, `sgmllib.py`, `psycopg2/`
- Add `pyproject.toml` with proper dependencies and a dev group

```toml
[project]
name = "bookshelf"
requires-python = ">=3.12"
dependencies = [
    "psycopg2-binary",
    "feedparser",
    "colorthief",
    "Pillow",
    "boto3",
]

[dependency-groups]
dev = ["pytest", "pytest-cov", "moto[s3]", "ruff"]
```

### Phase 2 — Shared Package (`src/bookshelf`)
- Create `src/bookshelf/` as an installable package
- Move and reorganize:
  - `cockroachdb_dao.py` → `src/bookshelf/dao/cockroachdb_dao.py`
  - `s3_dao.py` → `src/bookshelf/dao/s3_dao.py`
  - `bookshelf.py` (generation logic) → `src/bookshelf/bookshelf.py`
  - Extract `httpResult` helper (currently copy-pasted across ~6 lambdas) → `src/bookshelf/http.py`
  - Extract auth helpers (hash/salt, token gen/validation) → `src/bookshelf/auth.py`
- Update `CockroachDAO.__init__` to fetch `root.crt` content from AWS Secrets Manager instead of reading `./root.crt` from disk. If `SKIP_SSL_CERT=true`, skip the fetch entirely and connect without SSL (for local Postgres containers).

### Phase 3 — Lambda Restructure
- Create `lambdas/<name>/handler.py` for each active lambda
- Active lambdas to migrate:
  - `loginRegisterLambda.py`
  - `validateAuthtokenLambda.py`
  - `uploadSpineLambda.py`
  - `genShelfLambda.py`
  - `getGRbookshelf_lambda.py`
  - `setGoodreadsIdLambda.py`
  - `addShelfBgLambda.py`
  - `getShelfBgsLambda.py`
  - `addUnfoundToUpload.py`
  - `getUnfoundToUpload.py`
  - `calcDomColorLambda.py`
  - `cleanS3Shelves.py`
  - `leaderboardLambda.py`
  - `visitLambda.py`
  - `setShelfOwner.py`
  - `getOwnerShelves.py`
  - `getSpinesBySubmitter.py`
- Fix module-level DB init anti-pattern: `db = CockroachDAO(os.getenv(...))` at import time prevents tests from running without a live DB. Move instantiation inside `lambda_handler` or use lazy initialization.
- Fix hardcoded font path: `example/LeagueGothic.ttf` must be path-relative to the package, not the working directory

### Phase 4 — Local Development
- `local-dev/docker-compose.yml`:
  - `postgres:15` on port 5432 (CockroachDB-compatible for local testing)
  - `localstack/localstack` on port 4566 (mocks S3)
- `.env.example` documenting all required environment variables:
  ```
  DATABASE_URL=postgresql://postgres:dev@localhost:5432/bookshelf
  AWS_REGION=us-east-1
  AWS_ENDPOINT_URL=http://localhost:4566
  AWS_ACCESS_KEY_ID=test
  AWS_SECRET_ACCESS_KEY=test

  # Set to true for local dev — skips Secrets Manager fetch and connects to Postgres without SSL.
  # In production (Lambda), leave unset; set CERT_SECRET_ARN instead.
  SKIP_SSL_CERT=true
  CERT_SECRET_ARN=
  ```
- `Makefile`:
  ```makefile
  dev:     docker compose -f local-dev/docker-compose.yml up -d
  test:    pytest tests/
  lint:    ruff check .
  deploy:  sam build --use-container && sam deploy
  ```

### Phase 5 — Tests
Three layers, all runnable locally with `make test`:

**Unit tests** (no I/O, no DB):
- Auth: `hash_and_salt` determinism, different salts produce different hashes
- DAO: tuple-to-dict formatter methods (pure data transformation)
- Shelf: layout algorithm edge cases

**Integration tests** (real Postgres container, mocked S3):
- `CockroachDAO`: CRUD operations against local Postgres
- `s3_dao`: upload/download/delete against LocalStack via `moto`

**Handler tests** (call `lambda_handler(event, {})` directly):
- Login: valid credentials, wrong password, unknown user
- Register: new user, duplicate username
- Upload spine: valid image, missing auth, duplicate

### Phase 6 — SAM Infrastructure
- `infra/template.yaml` declaring:
  - `BookshelfLayer` (Lambda Layer containing the `src/bookshelf` package)
  - All Lambda functions referencing the layer
  - API Gateway routes per function
  - Shared environment variables (`DATABASE_URL`, `CERT_SECRET_ARN`, etc.)
- `sam build --use-container` compiles psycopg2 against the Lambda runtime Docker image (fixes the binary compatibility issue)
- `sam local start-api` enables full local API simulation

### Phase 7 — CI/CD (GitHub Actions)
```yaml
# .github/workflows/ci.yml
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env: { POSTGRES_DB: bookshelf, POSTGRES_PASSWORD: dev }
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: make test

  deploy:
    if: github.ref == 'refs/heads/master'
    needs: test
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/setup-sam@v2
      - run: make deploy
      env:
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

---

## Files to Delete

| File | Reason |
|---|---|
| `bookshelf.py` (root) | Legacy pre-Lambda version |
| `get_books.py` (root) | Legacy pre-Lambda version |
| `myBooks.py` (root) | Legacy pre-Lambda version |
| `nextread.py` (root) | Legacy pre-Lambda version |
| `randCol.py` (root) | Legacy pre-Lambda version |
| `get_books_lambda.py` (root) | Superseded by `aws_lambdas/python/` version |
| `bookshelf_stats.py` (root) | Legacy pre-Lambda version |
| `aws_lambdas/python/dynamodb_dao.py` | DynamoDB is fully legacy |
| `aws_lambdas/python/getSpineLambda.py` | Deprecated, not in use |
| `aws_lambdas/python/feedparser/` | Replace with `feedparser` pip package |
| `aws_lambdas/python/colorthief.py` | Replace with `colorthief` pip package |
| `aws_lambdas/python/sgmllib.py` | Vendored dependency, no longer needed |
| `aws_lambdas/python/psycopg2/` | Replace with Lambda Layer built by SAM |
| `aws_lambdas/python/lambda.zip` | Generated artifact, should not be in git |
