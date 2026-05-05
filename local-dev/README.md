# Local Development Environment for Bookshelf

This directory contains everything you need to run and test the Bookshelf Lambda backend locally, without touching AWS.

## Overview

The local development environment provides:
- **PostgreSQL database** (replaces CockroachDB - fully compatible)
- **LocalStack** simulating S3 and DynamoDB
- **Test harness** to invoke Lambda functions with mock events
- **Quick iteration** - test code changes instantly without deploying to AWS

## Prerequisites

- **Docker** and Docker Compose
- **Python 3.8+**
- **pip** (Python package manager)
- **AWS CLI** (for LocalStack verification, optional)

## Initial Setup (One Time)

### 1. Install Python Dependencies

From the project root:

```bash
pip install -r requirements-local.txt
```

This installs all the Python packages needed to run Lambdas locally, including:
- psycopg2-binary (PostgreSQL driver)
- boto3 (AWS SDK)
- Pillow and colorthief (image processing)
- python-dotenv (environment variables)
- feedparser, requests, beautifulsoup4 (web scraping)

### 2. Start Services

```bash
cd local-dev
docker-compose up -d
```

This starts:
- PostgreSQL on port 5432
- LocalStack on port 4566
- Initialization scripts that create tables and buckets

### 3. Wait for Services to Be Ready

```bash
# Check service status
docker-compose ps

# Should show postgres and localstack as "Up (healthy)"
```

Wait about 30 seconds for initialization to complete.

### 4. Verify Setup

**Check PostgreSQL:**
```bash
docker exec -it bookshelf-postgres psql -U bookshelf -d bookshelf -c "\dt"
```

You should see 6 tables:
- bookshelf_users
- shelf_images
- bookshelf
- visitors
- shelf_bgs
- unfound_to_upload

**Check LocalStack S3:**
```bash
aws --endpoint-url=http://localhost:4566 s3 ls
```

You should see the `bookshelf-spines` bucket.

**Check LocalStack DynamoDB:**
```bash
aws --endpoint-url=http://localhost:4566 dynamodb list-tables
```

You should see the `bookshelf` table.

## Running a Lambda

### Basic Usage

```bash
cd local-dev/test-harness
python invoke_lambda.py <lambda_name> test_events/<event_file>.json
```

### Examples

**Test user registration:**
```bash
python invoke_lambda.py loginRegisterLambda test_events/loginRegisterLambda.json
```

**Upload a book spine:**
```bash
python invoke_lambda.py uploadSpineLambda test_events/uploadSpineLambda.json
```

**Get leaderboard:**
```bash
python invoke_lambda.py leaderboardLambda test_events/leaderboardLambda.json
```

**Validate auth token:**
```bash
python invoke_lambda.py validateAuthtokenLambda test_events/validateAuthtokenLambda.json
```

### Creating Custom Test Events

Test events are JSON files in `test-harness/test_events/`. You can:
1. Copy an existing event file
2. Modify the parameters
3. Run the Lambda with your custom event

Example custom event for testing a specific user:
```bash
cd test_events
cp loginRegisterLambda.json test_myuser.json
# Edit test_myuser.json with your data
cd ..
python invoke_lambda.py loginRegisterLambda test_events/test_myuser.json
```

## Inspecting the Database

### Connect to PostgreSQL

```bash
docker exec -it bookshelf-postgres psql -U bookshelf -d bookshelf
```

### Useful SQL Commands

```sql
-- List all tables
\dt

-- Show table schema
\d bookshelf_users

-- Query users
SELECT username, email, banned FROM bookshelf_users;

-- Query uploaded books
SELECT upload_id, title, author, submitter FROM bookshelf;

-- Get leaderboard
SELECT submitter, COUNT(*) as count 
FROM bookshelf 
GROUP BY submitter 
ORDER BY count DESC;

-- Exit psql
\q
```

### Reset Database

To start fresh with an empty database:

```bash
# Stop services and delete all data
docker-compose down -v

# Start services again (will re-run init.sql)
docker-compose up -d
```

## Inspecting LocalStack (S3 and DynamoDB)

### S3 Commands

```bash
# List buckets
aws --endpoint-url=http://localhost:4566 s3 ls

# List files in bookshelf-spines bucket
aws --endpoint-url=http://localhost:4566 s3 ls s3://bookshelf-spines/

# Download a file
aws --endpoint-url=http://localhost:4566 s3 cp s3://bookshelf-spines/filename.jpg ./

# Upload a file
aws --endpoint-url=http://localhost:4566 s3 cp ./test.jpg s3://bookshelf-spines/
```

### DynamoDB Commands

```bash
# List tables
aws --endpoint-url=http://localhost:4566 dynamodb list-tables

# Scan bookshelf table
aws --endpoint-url=http://localhost:4566 dynamodb scan --table-name bookshelf

# Get specific item
aws --endpoint-url=http://localhost:4566 dynamodb get-item \
  --table-name bookshelf \
  --key '{"title": {"S": "Test Book"}, "book_id": {"S": "12345"}}'
```

## Daily Development Workflow

### Starting Your Day

```bash
cd local-dev

# Start services if they're not running
docker-compose up -d

# Verify they're healthy
docker-compose ps
```

### Making Changes

1. Edit Lambda code in `aws_lambdas/python/` or `aws_lambdas/js/`
2. Run the Lambda locally to test your changes
3. Repeat until it works
4. No deployment needed!

### Debugging

**View logs:**
```bash
# All services
docker-compose logs

# Just PostgreSQL
docker-compose logs postgres

# Just LocalStack
docker-compose logs localstack

# Follow logs in real-time
docker-compose logs -f
```

**Python debugging:**
Add print statements or use Python debugger in your Lambda code. The output will appear when you run `invoke_lambda.py`.

### Stopping Services

```bash
# Stop services (keeps data)
docker-compose down

# Stop services and delete all data
docker-compose down -v
```

## Environment Variables

The local environment uses `.env.local` for configuration:

```bash
# Database
DATABASE_URL=postgresql://bookshelf:local_password@localhost:5432/bookshelf?sslmode=require

# AWS (LocalStack)
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1

# SSL Certificate
SSL_CERT_PATH=./local-dev/postgres/root.crt
```

When these environment variables are set, the DAO files automatically use local services. In production AWS, these variables are not set, so the code uses production resources.

## Troubleshooting

### PostgreSQL connection refused

**Problem:** Can't connect to PostgreSQL at localhost:5432

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# View logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### LocalStack not responding

**Problem:** LocalStack health check fails or services not available

**Solution:**
```bash
# Check LocalStack status
docker-compose ps localstack

# View logs
docker-compose logs localstack

# Restart LocalStack
docker-compose restart localstack

# Re-run initialization
docker-compose restart localstack-init
```

### Lambda import errors

**Problem:** `ModuleNotFoundError` when running Lambda

**Solution:**
```bash
# Install missing dependencies
pip install -r requirements-local.txt

# If still failing, check if the module is in aws_lambdas/python/
ls aws_lambdas/python/
```

### SSL certificate errors

**Problem:** PostgreSQL SSL errors

**Solution:**
```bash
# Regenerate certificates
cd local-dev/postgres
rm root.crt root.key
openssl req -new -x509 -days 365 -nodes -text \
  -out root.crt -keyout root.key -subj "/CN=localhost"

# Restart PostgreSQL
cd ..
docker-compose restart postgres
```

### Port already in use

**Problem:** Port 5432 or 4566 already in use

**Solution:**
```bash
# Find what's using the port
lsof -i :5432
lsof -i :4566

# Stop the conflicting service or change ports in docker-compose.yml
```

## Available Lambda Functions

### Python Lambdas (18 total)

Core functionality:
- `loginRegisterLambda` - User registration and login
- `validateAuthtokenLambda` - Validate user auth tokens
- `uploadSpineLambda` - Upload book spine images
- `getSpineLambda` - Get book spine by ID
- `getSpinesBySubmitter` - Get all spines uploaded by a user
- `leaderboardLambda` - Get user leaderboard by upload count

Shelf management:
- `genShelfLambda` - Generate bookshelf image
- `getOwnerShelves` - Get shelves owned by user
- `setShelfOwner` - Set shelf owner
- `cleanS3Shelves` - Clean up old shelf images

Background management:
- `addShelfBgLambda` - Add custom shelf background
- `getShelfBgsLambda` - Get all shelf backgrounds

Goodreads integration:
- `getGRbookshelf_lambda` - Fetch Goodreads bookshelf
- `setGoodreadsIdLambda` - Set user's Goodreads ID
- `addUnfoundToUpload` - Add books not found on Goodreads
- `getUnfoundToUpload` - Get user's unfound books

Utilities:
- `calcDomColorLambda` - Calculate dominant color of image
- `visitLambda` - Track visitor analytics

### JavaScript Lambdas (3 total)

Located in `aws_lambdas/js/`:
- `fetchGR` - Fetch Goodreads data via RSS
- `fetchGRPuppeteer` - Fetch Goodreads data via web scraping

**Note:** JavaScript Lambdas require Node.js to run. The Python test harness only supports Python Lambdas.

## Production Deployment

When you're ready to deploy to AWS:

1. All code changes are automatically compatible
2. The DAO files check for environment variables
3. If not set (production), they use AWS resources
4. Deploy as usual with your existing AWS Lambda deployment process

No code changes needed - the same code runs locally and in production!

## Architecture

```
local-dev/
├── docker-compose.yml          # Service definitions
├── .env.local                  # Local environment config
├── postgres/
│   ├── init.sql               # Database schema
│   ├── root.crt               # SSL certificate
│   └── root.key               # SSL key
├── localstack/
│   └── init-aws.sh            # S3 and DynamoDB setup
├── test-harness/
│   ├── invoke_lambda.py       # Lambda runner
│   ├── mock_context.py        # Mock AWS context
│   └── test_events/           # Test event JSON files
└── README.md                   # This file
```

## Tips and Best Practices

1. **Keep services running** - Speeds up development by avoiding startup time
2. **Use test events** - Easier than crafting JSON by hand each time
3. **Check logs** - When something goes wrong, `docker-compose logs` is your friend
4. **Reset when needed** - `docker-compose down -v` gives you a clean slate
5. **Test edge cases** - Easy to test error conditions without affecting production
6. **Commit test events** - Share useful test events with your team via git

## Getting Help

- Check this README first
- Review the main project `LOCAL_DEV_PLAN.md` for architecture details
- Inspect Lambda code to understand expected input/output
- Check Docker logs for service issues
- Review the `.env.local` file for configuration

## Contributing

When adding new Lambda functions:

1. Add the Lambda to `aws_lambdas/python/` or `aws_lambdas/js/`
2. Create a test event in `test-harness/test_events/`
3. Test locally with `invoke_lambda.py`
4. Update this README if the Lambda has special requirements

Happy developing! 🚀
