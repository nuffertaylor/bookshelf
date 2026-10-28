# TODO: set up AWS deploy

Status: nothing is deployed from this repo yet. All production lambdas are currently deployed manually (zip + `aws lambda update-function-code`). The `refactor` branch has a SAM template (`infra/template.yaml`) but no stack, no `samconfig.toml`, no SSM parameters, and no AWS credentials in CI.

## Why `make deploy` doesn't work yet

`make deploy` runs:
```
sam build --use-container --template infra/template.yaml
sam deploy --parameter-overrides DatabaseUrl={{resolve:ssm:/bookshelf/database_url}} CertSecretArn={{resolve:ssm:/bookshelf/cert_secret_arn}} SkipSslCert=""
```
- `sam deploy` has no `--stack-name`, `--s3-bucket` or `--capabilities`, and there is no `samconfig.toml`.
- The SSM parameters don't exist yet.
- The Makefile sets `DOCKER_HOST` to the Colima socket path (macOS only).
- `.github/workflows/ci.yml` runs `make deploy` on every push to `master` (after tests). It has no AWS secrets configured, so it will fail once `refactor` is merged. Remove or guard that job until deploy is ready.

## Checklist

- [ ] **AWS credentials.** An IAM user or role that can create CloudFormation stacks, Lambda, API Gateway, IAM roles and S3. Configure locally (`aws configure` or SSO). Add GitHub secrets only if CI should deploy.
- [ ] **Production parameters.** Create SSM parameters `/bookshelf/database_url` (CockroachDB connection string) and `/bookshelf/cert_secret_arn` (Secrets Manager secret with the SSL cert), or pass the values at deploy time.
- [ ] **Run `sam deploy --guided` once.** It asks for stack name and region, creates the artifacts bucket, and writes `samconfig.toml`. Commit that file.
- [ ] **Decide how to avoid name collisions.** The template sets explicit `FunctionName`s (`loginRegister`, `getGRBookshelf`, ...) that match the live, manually created functions, and CloudFormation won't create a function whose name exists. Options:
  - Deploy a **separate test stack** with a name prefix (add a `Prefix` parameter to the template, `${Prefix}loginRegister`, etc.) and a non-production database. Recommended first step.
  - Delete or rename the old functions at cutover (downtime).
  - Import the existing functions into the stack (fiddly).
- [ ] **Plan the API URL.** SAM creates a new API Gateway (stage `Prod`, new ID). The old frontend uses `https://vi64h2xk34.execute-api.us-east-1.amazonaws.com/alpha/`. Either point the frontend's `REACT_APP_API_URL` at the new API (see `.env.production.example` in `bookshelf-ts-site`) or map a custom domain.
- [ ] **Confirm the S3 bucket.** The template doesn't appear to define `bookshelf-spines`. Check how the lambdas reference it before deploying.
- [ ] **Fix `make deploy` for non-Colima machines.** Drop or condition the `DOCKER_HOST` line (Windows, Linux CI).
- [ ] **Update `nodejs20.x`** for `GetGRBookDetailsFunction` (deprecated runtime; blocks creates and updates later).
- [ ] **CI.** Add AWS secrets and keep the `deploy` job, or remove it and deploy by hand.
- [ ] **Write `docs/deploy.md`** with the final commands once a test stack works.

## Suggested order

1. Create the test database and parameters.
2. Add the `Prefix` parameter to the template.
3. `sam build --use-container`, then `sam deploy --guided`; commit `samconfig.toml`.
4. Point the refactor frontend at the test stack's API URL and test it.
5. Plan the production cutover (names, API URL, database).

## Notes
- On Windows, `sam build` drops compiled `.so` files from the layer; see `docs/windows-setup.md`. Build deploys with `--use-container` (Linux) to avoid this.
- Goodreads RSS feeds are gone. The new `importGRLibraryCsv` lambda (`POST /importgrlibrary`) replaces `getGRBookshelf` for production, and the frontend needs a CSV upload and shelf-picker UI.
