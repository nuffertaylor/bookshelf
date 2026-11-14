# Testing and deploying Hardcover sign-in (Windows / PowerShell)

Steps for the Windows machine. Part 1 gets the code, Part 2 tests it locally (no AWS needed), and Part 3 is the production steps for later. Run commands in PowerShell from the `bookshelf` folder unless a step says otherwise.

These commands have not been run on Windows. If one behaves differently, note the error text and the step.

## 1. Get the new code

The backend's `hardcover_integration` history was rewritten (the Claude co-author lines were removed), so a plain `git pull` will conflict. Reset to the remote instead. **This throws away any local commits on that branch.**

```powershell
git fetch origin
git checkout hardcover_integration
git reset --hard origin/hardcover_integration
```

Then the frontend:

```powershell
cd ..\bookshelf-ts-site
git fetch origin
git checkout hardcover_integration
git pull
npm install
cd ..\bookshelf
```

## 2. Test locally (no AWS needed)

Docker Desktop must show "Engine running".

### a. Restart LocalStack with KMS, and start Postgres

```powershell
docker compose -f local-dev/docker-compose.yml up -d --force-recreate localstack
docker compose -f local-dev/docker-compose.yml up -d postgres
```

### b. Add the Hardcover tables

Needed if your local database was created before the Hardcover work. It is safe to run twice.

```powershell
Get-Content local-dev\migrations\001_hardcover_oauth.sql -Raw | docker compose -f local-dev/docker-compose.yml exec -T postgres psql -U postgres -d bookshelf
```

### c. Make a local encryption key

The dummy credentials keep your real AWS keys out of this. Only this PowerShell window is affected.

```powershell
$env:AWS_ACCESS_KEY_ID="test"; $env:AWS_SECRET_ACCESS_KEY="test"; $env:AWS_DEFAULT_REGION="us-east-1"
$kms = aws --endpoint-url http://localhost:4566 kms create-key --query KeyMetadata.KeyId --output text
$kms
```

The last line should print a key ID (a UUID). You need the `$kms` variable in the next step, so keep using the same window.

### d. Build and start the API

Type the Hardcover client secret yourself (it's in your Hardcover app settings). It is visible in the process arguments while SAM runs, which is fine on a personal machine, but don't do this on a shared one. Never put it in a file that git tracks.

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

Notes:
- Robocopy exit codes 1 to 7 mean success. Run `robocopy` again after every `sam build`, because a rebuild wipes the copied files.
- If you have never installed the Linux Python packages into `src/`, do step 5 of `docs/windows-setup.md` first.
- Leave this window open. The first request to each endpoint is slow while its container starts.

### e. Start the frontend (second window)

```powershell
cd ..\bookshelf-ts-site
npm start
```

The frontend's `.env.development` already points at `http://localhost:3001/`. Open http://localhost:3000. The redirect `http://localhost:3000/oauth/callback` is already registered with Hardcover.

### f. Things to try

1. **Sign in with Hardcover** on the Login tab. Log out, then sign in again. You should get the same account back.
2. **Create tab, then Hardcover.** Pick a list and load it. Also load your Read list (it has around 740 books, so it takes a few requests).
3. **Password login after linking.** Log in with an older username and password account, link Hardcover from the Profile, then log out and log in with the password again. The Profile should show Hardcover as linked, and shelves should load without reconnecting.
4. **Missing spines.** On a Hardcover shelf, open "Upload Missing Spines", upload one, and confirm the shelf reloads.

If something fails, copy the error from the `sam local` window and from the browser console.

## 3. Production (after local works)

Nothing here is needed for local testing, and the production deploy fails without it. `plans/04-hardcover-manual-steps.md` has the full commands for each item.

1. **AWS resources** (Part C): create the KMS key and the Hardcover client secret in Secrets Manager, then add the SSM parameters `/bookshelf/kms_key_id`, `/bookshelf/hardcover_secret_arn` and `/bookshelf/hardcover_client_id`.
2. **Production database** (Part D): take a backup, then run `local-dev/migrations/001_hardcover_oauth.sql` one statement at a time, **before** any new code goes live.
3. **Merge the backend** `hardcover_integration` into `master`. That triggers the automatic deploy (watch the CI workflow in the Actions tab).
4. **Merge the frontend** `hardcover_integration` into `master`. Vercel deploys it, and `vercel.json` lets `/oauth/callback` load the app.

Optional before step 3: run the token refresh test on any machine with `uv` installed (`make dev`, then `uv run pytest tests/integration -rs`). It must pass, not skip. It checks that two simultaneous refreshes spend a refresh token only once.
