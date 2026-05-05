# Local Development - Quick Start Guide

Get up and running with the Bookshelf local development environment in 5 minutes!

## Prerequisites

- Docker (start Docker Desktop or Colima)
- Python 3.8+
- pip

## Setup (First Time Only)

### 1. Start Docker

**If using Colima:**
```bash
colima start
```

**If using Docker Desktop:**
Just open the Docker Desktop application.

### 2. Install Dependencies

```bash
pip install -r requirements-local.txt
```

### 3. Start Services

```bash
cd local-dev
docker-compose up -d
```

Wait 30 seconds for services to initialize.

### 4. Verify

```bash
# Check services are running
docker-compose ps

# Should show postgres and localstack as "Up (healthy)"
```

## Run Your First Lambda

```bash
cd local-dev/test-harness

# Get the leaderboard (should return empty array initially)
python invoke_lambda.py leaderboardLambda test_events/leaderboardLambda.json
```

## Test User Registration and Login

```bash
# Register a new user
python invoke_lambda.py loginRegisterLambda test_events/loginRegisterLambda.json

# The response will include an authtoken - copy it

# Edit validateAuthtokenLambda.json to use the returned authtoken
nano test_events/validateAuthtokenLambda.json

# Validate the token
python invoke_lambda.py validateAuthtokenLambda test_events/validateAuthtokenLambda.json
```

## Common Commands

### Start Services (Daily)
```bash
cd local-dev
docker-compose up -d
```

### Stop Services
```bash
cd local-dev
docker-compose down
```

### View Logs
```bash
cd local-dev
docker-compose logs -f
```

### Connect to Database
```bash
docker exec -it bookshelf-postgres psql -U bookshelf -d bookshelf
```

### Reset Everything
```bash
cd local-dev
docker-compose down -v  # Deletes all data
docker-compose up -d    # Fresh start
```

## Test Other Lambdas

All available test events are in `local-dev/test-harness/test_events/`:

```bash
cd local-dev/test-harness

# Visit tracking
python invoke_lambda.py visitLambda test_events/visitLambda.json

# Get spine by ID
python invoke_lambda.py getSpineLambda test_events/getSpineLambda.json

# Upload book spine
python invoke_lambda.py uploadSpineLambda test_events/uploadSpineLambda.json

# Generate shelf
python invoke_lambda.py genShelfLambda test_events/genShelfLambda.json

# And many more...
```

## Making Changes

1. Edit Lambda code in `aws_lambdas/python/`
2. Run the Lambda with the test harness
3. See results immediately - no deployment needed!

## Need Help?

- Full documentation: `local-dev/README.md`
- Implementation details: `LOCAL_DEV_PLAN.md`
- Troubleshooting: See README.md "Troubleshooting" section

## Key Files

- `local-dev/.env.local` - Environment configuration
- `local-dev/docker-compose.yml` - Service definitions
- `local-dev/test-harness/invoke_lambda.py` - Lambda runner
- `local-dev/test-harness/test_events/*.json` - Test data

## Tips

💡 Keep services running while developing (faster iteration)  
💡 Use `docker-compose logs` to debug issues  
💡 Create custom test events by copying existing ones  
💡 Check the database with psql to verify data persistence  

Happy coding! 🚀
