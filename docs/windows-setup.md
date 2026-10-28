# Running locally on Windows

The Makefile assumes macOS (Colima socket, `make`), so on Windows run the equivalent commands by hand in PowerShell.
The stack: Postgres (5432) and LocalStack S3 (4566) in Docker, the Lambda API via `sam local` (3001), and the React app from `bookshelf-ts-site` (3000).

## 1. Install prerequisites

```powershell
winget install -e --id Docker.DockerDesktop
winget install -e --id Python.Python.3.12
winget install -e --id Amazon.SAM-CLI
winget install -e --id OpenJS.NodeJS.LTS
```

- Reboot if Docker Desktop asks, then start it and wait for "Engine running". Use the WSL2 backend.
- Open a new PowerShell window after installing so the new tools are on your PATH.
- Do not set `DOCKER_HOST` (that is only for Colima on macOS).

Verify: `docker run --rm hello-world`, `python --version`, `sam --version`, `node --version`.

## 2. Clone both repos side by side

Keep them somewhere simple like `C:\dev` (not OneDrive).

```powershell
git clone <bookshelf-repo-url> bookshelf
git clone <bookshelf-ts-site-repo-url> bookshelf-ts-site
cd bookshelf; git checkout refactor
cd ..\bookshelf-ts-site; git checkout refactor
```

## 3. Start Postgres and LocalStack

From the `bookshelf` folder:

```powershell
Copy-Item .env.example .env
docker compose -f local-dev/docker-compose.yml up -d
docker compose -f local-dev/docker-compose.yml ps
```

Both containers should be running. If port 5432 is already in use (for example by a native Postgres), stop that first.

## 4. Seed test data

```powershell
pip install psycopg2-binary boto3
python local-dev/seed/seed.py
curl.exe http://localhost:4566/bookshelf-spines
```

The last command should list the seeded images in the `bookshelf-spines` bucket.

## 5. Install the Linux Python dependencies into `src/`

The Lambda containers need Linux-compiled packages (psycopg2, Pillow, ...). Re-run this only after changing `local-dev/layer-requirements.txt`.
`--upgrade` is required so pip replaces any package folders that already exist.

```powershell
docker run --rm -v "${PWD}/src:/opt/layer" -v "${PWD}/local-dev:/opt/local-dev" python:3.12-slim pip install --upgrade -r /opt/local-dev/layer-requirements.txt -t /opt/layer/ -q
```

## 6. Build and start the API

```powershell
sam build --template infra/template.yaml
robocopy src .aws-sam\build\BookshelfLayer\python /E /XD .aws-sam __pycache__

$env:AWS_ACCESS_KEY_ID="test"; $env:AWS_SECRET_ACCESS_KEY="test"; $env:AWS_DEFAULT_REGION="us-east-1"
sam local start-api --parameter-overrides AwsEndpointUrl="http://host.docker.internal:4566" --port 3001
```

- On Windows, `sam build` copies `src/` into the layer without the compiled `.so` files, which causes `No module named 'psycopg2._psycopg'` at runtime. The `robocopy` line copies them in. Its exit codes 1 to 7 mean success.
- Re-run both the build and the `robocopy` after any code change. A rebuild wipes the copied files, so do not rebuild without repeating `robocopy`.
- Must use port 3001 (React uses 3000). Keep `AwsEndpointUrl` as written: the Lambda containers reach LocalStack through `host.docker.internal`, and the app reads it as `S3_ENDPOINT_URL`.
- The first request to each endpoint is slow while its container starts.
- Leave this window open. Use another one for the next step.

## 7. Run the frontend

The frontend must be on its `refactor` branch, which reads `REACT_APP_API_URL` and `REACT_APP_IMG_URL_PREFIX` from the committed `.env.development` (pointing at `localhost:3001` and the LocalStack bucket).

```powershell
cd ..\bookshelf-ts-site
npm install
npm start
```

The app opens at http://localhost:3000.

## Known limitations

- Goodreads has disabled its RSS feeds, so `getGRBookshelf` (which fetches them live) returns empty results locally too. Shelf import will move to the Goodreads CSV export flow.
- `src/pages/Curate.tsx` still has one hardcoded production image URL.

## Troubleshooting

- **Port already allocated (3001, 4566, 5432):** `netstat -ano | findstr :5432` to find the process.
- **`sam local` can't reach Docker:** check Docker Desktop shows "Engine running".
- **Browser reports a CORS error on an API call:** the Lambda probably crashed (502 has no CORS headers). Check the `sam local start-api` window for the real error.
