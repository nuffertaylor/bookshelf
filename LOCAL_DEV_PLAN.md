# Local Development Setup for Bookshelf Lambda Backend

## Context

The bookshelf project contains 21 AWS Lambda functions (18 Python, 3 JavaScript) that currently only run in AWS. There's no way to run them locally or test against a local database. The Lambdas depend on:

- **CockroachDB** (14 Lambdas) - PostgreSQL-compatible database with 6 tables
- **S3** (7 Lambdas) - bookshelf-spines bucket for image storage
- **DynamoDB** (1 Lambda) - legacy table used by getSpineLambda only
- **Goodreads** (3 Lambdas) - web scraping, no AWS dependency

This makes personal development difficult - every code change requires deploying to AWS and testing against production infrastructure. We need a local development environment where you can run Lambdas, test changes, and iterate quickly without touching AWS.

## Recommended Approach

**Docker Compose + LocalStack + PostgreSQL with Direct Lambda Invocation**

This hybrid approach provides:
- Local PostgreSQL replacing CockroachDB (fully compatible)
- LocalStack simulating S3 and DynamoDB
- Direct Python/Node execution (faster than containerized Lambda simulation)
- Test harness to invoke Lambdas with mock events
- Minimal code changes (environment variables only)

**Why this approach?**
- PostgreSQL is 100% compatible with the existing schema (both use PostgreSQL dialect)
- LocalStack's free tier covers all needed AWS services
- Direct execution is faster for development than SAM CLI or full Lambda containers
- Maintains backward compatibility - AWS deployment unchanged

## Implementation Plan

### 1. Create Local Development Directory Structure

```
local-dev/
├── docker-compose.yml          # PostgreSQL + LocalStack services
├── .env.local                  # Local environment configuration
├── postgres/
│   ├── init.sql               # Database schema initialization
│   └── root.crt               # Self-signed cert for local SSL
├── localstack/
│   └── init-aws.sh            # Create S3 buckets and DynamoDB tables
├── test-harness/
│   ├── invoke_lambda.py       # Script to run any Lambda locally
│   ├── mock_context.py        # Mock Lambda context object
│   └── test_events/           # JSON event files for each Lambda
│       ├── uploadSpine.json
│       ├── loginRegister.json
│       └── (one per Lambda)
└── README.md                   # Local dev documentation
```

Also create at project root:
- `requirements-local.txt` - Python dependencies for local dev
- `.env.example` - Template for environment variables

### 2. Docker Compose Setup

Create `local-dev/docker-compose.yml` with three services:

**postgres**: PostgreSQL 15 container
- Port: 5432
- Database: bookshelf
- User: bookshelf / Password: local_password
- Enable uuid-ossp extension for `gen_random_uuid()`
- Volume mount init.sql for schema creation
- Generate self-signed SSL cert

**localstack**: LocalStack container (free tier)
- Port: 4566 (unified endpoint)
- Services: S3, DynamoDB
- Volume for data persistence

**localstack-init**: One-shot init container
- Runs init-aws.sh after LocalStack is healthy
- Creates bookshelf-spines S3 bucket
- Creates bookshelf DynamoDB table

### 3. Database Initialization

Create `local-dev/postgres/init.sql` with all table schemas from `cockroachdb_dao.py`:

Extract the 6 CREATE TABLE statements:
- bookshelf_users (authentication)
- shelf_images (generated shelf metadata)
- bookshelf (book spine uploads)
- visitors (analytics)
- shelf_bgs (shelf background configurations)
- unfound_to_upload (Goodreads books pending upload)

Adapt CockroachDB SQL to PostgreSQL:
- STRING → TEXT (PostgreSQL standard type)
- Keep INT, BOOLEAN, UUID, INT[] as-is
- Keep DEFAULT gen_random_uuid() (works in both)
- Add CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

Generate self-signed cert:
```bash
openssl req -new -x509 -days 365 -nodes -text \
  -out root.crt -keyout root.key -subj "/CN=localhost"
```

### 4. LocalStack Initialization

Create `local-dev/localstack/init-aws.sh`:

```bash
#!/bin/bash
# Wait for LocalStack to be ready
sleep 5

# Create S3 bucket
awslocal s3 mb s3://bookshelf-spines

# Create DynamoDB table (mirrors current AWS table)
awslocal dynamodb create-table \
  --table-name bookshelf \
  --attribute-definitions \
    AttributeName=title,AttributeType=S \
    AttributeName=book_id,AttributeType=S \
  --key-schema \
    AttributeName=title,KeyType=HASH \
    AttributeName=book_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
```

### 5. Environment Configuration

Create `local-dev/.env.local`:

```env
# Database
DATABASE_URL=postgresql://bookshelf:local_password@localhost:5432/bookshelf?sslmode=require

# LocalStack AWS endpoints
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1
LOCALSTACK_HOST=localhost:4566
```

Create `.env.example` (commit to repo):

```env
# Database - local: use Docker PostgreSQL, AWS: use CockroachDB
DATABASE_URL=postgresql://user:password@host:port/database

# AWS - local: use LocalStack, AWS: leave empty
AWS_ENDPOINT_URL=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
```

### 6. Lambda Invocation Harness

Create `local-dev/test-harness/invoke_lambda.py`:

This script will:
- Accept Lambda name and event JSON file path
- Load environment variables from .env.local
- Dynamically import the Lambda module
- Create mock context object
- Invoke lambda_handler(event, context)
- Print formatted response

Create `local-dev/test-harness/mock_context.py`:

```python
class MockLambdaContext:
    function_name = "local-test"
    memory_limit_in_mb = 128
    invoked_function_arn = "arn:aws:lambda:us-east-1:000000000000:function:local-test"
    aws_request_id = "local-request-id"
    log_group_name = "/aws/lambda/local-test"
    log_stream_name = "local"
    
    def get_remaining_time_in_millis(self):
        return 300000  # 5 minutes
```

Usage:
```bash
python invoke_lambda.py uploadSpineLambda test_events/uploadSpine.json
```

### 7. Test Event Files

Create `local-dev/test-harness/test_events/` with JSON files for each Lambda:

Example - `loginRegister.json`:
```json
{
  "requestType": "register",
  "username": "testuser",
  "password": "testpass123",
  "email": "test@example.com",
  "ip": "127.0.0.1"
}
```

Example - `uploadSpine.json`:
```json
{
  "image": "data:image/png;base64,iVBORw0KG...",
  "title": "Test Book",
  "book_id": "12345",
  "dimensions": "100x150",
  "username": "testuser",
  "authtoken": "valid-auth-token-here"
}
```

Create one JSON file per Lambda with realistic test data.

### 8. Python Dependencies

Create `requirements-local.txt`:

```
# Database
psycopg2-binary>=2.9.0

# AWS SDK
boto3>=1.26.0

# Image processing
Pillow>=9.0.0
colorthief>=0.2.1

# Utilities
python-dotenv>=0.19.0

# Testing (future)
pytest>=7.0.0
pytest-cov>=3.0.0

# RSS parsing (for Goodreads Lambda)
feedparser>=6.0.0
```

### 9. Minor DAO Updates

Update `aws_lambdas/python/cockroachdb_dao.py`:

Change line 7 from:
```python
self.conn = psycopg2.connect(db_url, sslrootcert="./root.crt")
```

To:
```python
# Allow SSL cert path override for local dev
import os
ssl_cert = os.getenv('SSL_CERT_PATH', './root.crt')
if os.path.exists(ssl_cert):
    self.conn = psycopg2.connect(db_url, sslrootcert=ssl_cert)
else:
    # For local dev without SSL, ensure connection string has sslmode=disable
    self.conn = psycopg2.connect(db_url)
```

Update `aws_lambdas/python/s3_dao.py`:

Change lines 8-9 to respect AWS_ENDPOINT_URL:
```python
import os
endpoint_url = os.getenv('AWS_ENDPOINT_URL')
s3 = boto3.resource('s3', endpoint_url=endpoint_url)
s3_client = boto3.client('s3', endpoint_url=endpoint_url)
```

Update `aws_lambdas/python/dynamodb_dao.py`:

Change lines 6-10 to respect AWS_ENDPOINT_URL:
```python
import os
region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
endpoint_url = os.getenv('AWS_ENDPOINT_URL')
dynamodb = boto3.resource('dynamodb', region_name=region, endpoint_url=endpoint_url)
db_client = boto3.client('dynamodb', region_name=region, endpoint_url=endpoint_url)
```

**Important**: These changes are backward compatible. When deployed to AWS, these environment variables won't be set, so behavior is unchanged.

### 10. Documentation

Create `local-dev/README.md` with:

- Prerequisites (Docker, Python 3.8+, pip)
- Initial setup steps
- How to start/stop services
- How to run a Lambda
- How to debug issues
- How to reset the database
- Troubleshooting common problems

## Developer Workflow

### Initial Setup (One Time)

```bash
# Navigate to local dev directory
cd local-dev

# Start all services
docker-compose up -d

# Wait for services to be healthy (30 seconds)
docker-compose ps

# Install Python dependencies
cd ..
pip install -r requirements-local.txt

# Verify database connection
docker exec -it local-dev-postgres-1 psql -U bookshelf -d bookshelf -c "\dt"

# Verify S3 bucket exists
aws --endpoint-url=http://localhost:4566 s3 ls
```

### Daily Development

```bash
# Start services if stopped
cd local-dev
docker-compose up -d

# Run a Lambda
cd test-harness
python invoke_lambda.py loginRegisterLambda test_events/loginRegister.json

# Check database state
docker exec -it local-dev-postgres-1 psql -U bookshelf -d bookshelf

# View logs
docker-compose logs postgres
docker-compose logs localstack
```

### Cleanup

```bash
# Stop services, keep data
docker-compose down

# Stop services, delete all data
docker-compose down -v
```

## Verification

After implementation, verify:

1. **Services Start**: `docker-compose up` starts PostgreSQL and LocalStack without errors
2. **Database Schema**: All 6 tables exist in PostgreSQL
3. **S3 Bucket**: bookshelf-spines bucket exists in LocalStack
4. **DynamoDB Table**: bookshelf table exists in LocalStack
5. **Lambda Invocation**: Can run uploadSpineLambda and get success response
6. **Database Persistence**: Data written to PostgreSQL persists across Lambda calls
7. **S3 Upload**: Images uploaded to LocalStack S3 can be retrieved
8. **AWS Compatibility**: Lambda code still deploys to AWS without changes

## Critical Files

Files that need to be created:
- `local-dev/docker-compose.yml`
- `local-dev/.env.local`
- `local-dev/postgres/init.sql`
- `local-dev/localstack/init-aws.sh`
- `local-dev/test-harness/invoke_lambda.py`
- `local-dev/test-harness/mock_context.py`
- `local-dev/test-harness/test_events/*.json` (21 files)
- `local-dev/README.md`
- `requirements-local.txt`
- `.env.example`

Files that need minor updates:
- `aws_lambdas/python/cockroachdb_dao.py` (SSL cert handling)
- `aws_lambdas/python/s3_dao.py` (endpoint URL)
- `aws_lambdas/python/dynamodb_dao.py` (endpoint URL)

## Implementation Priority

1. **Phase 1** (Core infrastructure): Docker Compose, PostgreSQL, LocalStack
2. **Phase 2** (Lambda harness): invoke_lambda.py, mock_context.py, test events
3. **Phase 3** (DAO updates): Update the 3 DAO files for local compatibility
4. **Phase 4** (Testing): Verify each Lambda works locally
5. **Phase 5** (Documentation): README and troubleshooting guide

## Benefits

- **Fast iteration**: No AWS deployment needed to test changes
- **Free development**: No AWS costs during development
- **Isolated testing**: Won't affect production data
- **Complete control**: Can reset database, inspect state, debug easily
- **Team onboarding**: New developers can set up in < 30 minutes
