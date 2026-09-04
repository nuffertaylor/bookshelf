# bookshelf

A service for uploading book spine photos, matching them to Goodreads shelves, and sharing the results.

> **Note:** Server-side shelf image generation (`src/bookshelf/bookshelf.py`, `lambdas/gen_shelf/`) is deprecated — this logic has moved to the frontend. The code is kept for reference but is not actively used.

## Local Development

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (or pip)
- Docker (for the local Postgres + S3 services)

### Setup

```bash
# Install dependencies (including dev tools)
uv sync

# Copy the example env file and fill in any values you want to override
cp .env.example .env
```

The defaults in `.env.example` are set to work with the local Docker services out of the box — no changes needed for basic development.

### Docker runtime note (Colima)

If you're using Colima instead of Docker Desktop, SAM needs to know the socket location. Uncomment this line in your `.env`:
```
DOCKER_HOST=unix://${HOME}/.colima/default/docker.sock
```

### Start local services

```bash
make dev
```

This starts:
- **Postgres 15** on `localhost:5432` — stands in for CockroachDB locally
- **LocalStack** on `localhost:4566` — mocks S3

### Run tests

```bash
make test
```

### Lint

```bash
make lint
```

### Invoke a lambda locally (AWS SAM)

```bash
# Install SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
make deploy  # builds and deploys to AWS

# Or to run locally without deploying:
sam build --use-container
sam local start-api
```

`sam local start-api` starts a local API Gateway that routes requests to your lambda handlers, using the environment from `.env`.

## Project structure

```
lambdas/        # One directory per Lambda function
src/bookshelf/  # Shared library (deployed as a Lambda Layer)
  auth.py       # Password hashing, token generation
  http.py       # Shared HTTP response helper
  bookshelf.py  # Shelf image generation
  dao/          # Database and S3 access
infra/          # AWS SAM template
tests/          # Unit, integration, and handler tests
local-dev/      # docker-compose for local Postgres + LocalStack
example/        # Sample bookshelf image and book spines
```

## Environment variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `SKIP_SSL_CERT` | Set to `true` for local dev to skip the SSL cert fetch |
| `CERT_SECRET_ARN` | ARN of the Secrets Manager secret holding `root.crt` (production only) |
| `AWS_ENDPOINT_URL` | Override S3/Secrets Manager endpoint (use `http://localhost:4566` for LocalStack) |
