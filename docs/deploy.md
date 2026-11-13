# Deploying a test stack to AWS (Windows / PowerShell)

This creates a **separate test stack** (`bookshelf-test`): new lambdas named `test-loginRegister`, `test-getHardcoverShelf`, ... and a **new API Gateway** with its own URL. The live, manually deployed lambdas and the old API (`.../alpha/`) are untouched. Use a separate (non-production) database.

The test stack still uses the real `bookshelf-spines` S3 bucket (the name is hardcoded in `src/bookshelf/dao/s3_dao.py`), so test uploads land there. Use a throwaway test account.

Run everything in PowerShell from the repo root, on the branch that has `infra/template.yaml` with the `Prefix` parameter.

## 1. Prerequisites

```powershell
winget install -e --id Amazon.AWSCLI
winget install -e --id Amazon.SAM-CLI
winget install -e --id Docker.DockerDesktop
```

Open a new PowerShell window, start Docker Desktop (wait for "Engine running"), then:

```powershell
aws configure          # access key, secret, region us-east-1
aws sts get-caller-identity
sam --version; docker run --rm hello-world
```

The IAM user needs to create CloudFormation stacks, Lambda, API Gateway, IAM roles/policies, S3 (SAM artifacts bucket), SSM, KMS and Secrets Manager. An admin user is simplest for a first run.

## 2. Create the test resources

**a. Test database.** Create a separate CockroachDB database/cluster, apply the schema (and `local-dev/migrations/001_hardcover_oauth.sql`, one statement at a time), and have its connection string and CA cert ready.

**b. SSL cert secret** (Secrets Manager; skip if your test DB has no cert requirement, but then deploy with `SkipSslCert=true`):

```powershell
aws secretsmanager create-secret --name bookshelf-test/db-cert --secret-string file://C:\path\to\ca.crt
```

Note the `ARN` in the output.

**c. KMS key** for stored Hardcover tokens:

```powershell
aws kms create-key --description bookshelf-test-hardcover-tokens
```

Note the `KeyId`.

**d. Hardcover client secret**, from an untracked file containing only the secret:

```powershell
aws secretsmanager create-secret --name bookshelf-test/hardcover-client-secret --secret-string file://C:\path\to\secret.txt
Remove-Item C:\path\to\secret.txt
```

Note the `ARN`.

**e. SSM parameters** (replace the bracketed values, without the brackets). Note the database URL contains a password and ends up in the lambdas' environment variables regardless, so treat the AWS account as the trust boundary.

```powershell
aws ssm put-parameter --name /bookshelf-test/database_url --type String --value "[cockroach connection string]"
aws ssm put-parameter --name /bookshelf-test/cert_secret_arn --type String --value "[cert secret ARN]"
aws ssm put-parameter --name /bookshelf-test/kms_key_id --type String --value "[KeyId]"
aws ssm put-parameter --name /bookshelf-test/hardcover_secret_arn --type String --value "[client secret ARN]"
aws ssm put-parameter --name /bookshelf-test/hardcover_client_id --type String --value a062038b-5d7e-4646-ace2-e250b8457cc4
```

## 3. Build (in a Linux container)

Building with `--use-container` avoids the missing-`.so` problem described in `docs/windows-setup.md`.

```powershell
Copy-Item local-dev\layer-requirements.txt src\requirements.txt
sam build --use-container --template infra/template.yaml
Remove-Item src\requirements.txt
```

If the build fails, send me the last 30 lines of output. Re-run all three lines after any code change.

## 4. Deploy

```powershell
sam deploy `
  --stack-name bookshelf-test `
  --region us-east-1 `
  --resolve-s3 `
  --capabilities CAPABILITY_IAM `
  --no-confirm-changeset `
  --parameter-overrides `
    Prefix="test-" `
    DatabaseUrl="{{resolve:ssm:/bookshelf-test/database_url}}" `
    CertSecretArn="{{resolve:ssm:/bookshelf-test/cert_secret_arn}}" `
    SkipSslCert="" `
    HardcoverClientId="{{resolve:ssm:/bookshelf-test/hardcover_client_id}}" `
    HardcoverSecretArn="{{resolve:ssm:/bookshelf-test/hardcover_secret_arn}}" `
    HardcoverRedirectUri="http://localhost:3000/oauth/callback" `
    KmsKeyId="{{resolve:ssm:/bookshelf-test/kms_key_id}}"
```

(`SkipSslCert=""` means "use the cert". `localhost:3000/oauth/callback` is already registered with Hardcover, so you can test with the frontend running locally.)

When it finishes, read the API URL:

```powershell
aws cloudformation describe-stacks --stack-name bookshelf-test --query "Stacks[0].Outputs" --output table
```

If the stack ends in `ROLLBACK_COMPLETE`, find the cause with:

```powershell
aws cloudformation describe-stack-events --stack-name bookshelf-test --query "StackEvents[?contains(ResourceStatus,'FAILED')].[LogicalResourceId,ResourceStatusReason]" --output table
```

then delete the failed stack (`aws cloudformation delete-stack --stack-name bookshelf-test`) before redeploying. Send me the output and I'll diagnose.

## 5. Smoke test

```powershell
curl.exe "<ApiUrl>leaderboard"
curl.exe -X POST "<ApiUrl>auth/hardcover/start" -H "Content-Type: application/json" -d "{\"mode\":\"login\"}"
```

The first should return JSON (a database connection works); the second should return an `authorize_url`. A 502 means the lambda crashed; read its log:

```powershell
aws logs tail /aws/lambda/test-leaderboard --since 15m
```

## 6. Point the frontend at it

In `bookshelf-ts-site` (branch `refactor`/the Hardcover branch), create `.env.development.local` containing:

```
REACT_APP_API_URL=<ApiUrl>
```

(keep the trailing slash), then `npm start` and walk through sign-in on http://localhost:3000. The browser console / `aws logs tail` will show failures.

## 7. Check API Gateway logging

Requests carry authorization codes and session tokens. Confirm the `Prod` stage has no full request/response body logging (API Gateway console, stage, Logs/Tracing).

## Cleanup / later

- Remove the test stack: `aws cloudformation delete-stack --stack-name bookshelf-test`.
- Production cutover is a separate decision (see `docs/TODO-setup-aws-deploy.md`): a stack with an empty `Prefix` collides with the live function names, and the new API URL is `/Prod/` rather than `/alpha/`.
- CI: the `deploy` job in `.github/workflows/ci.yml` still runs `make deploy` on `master` without AWS secrets and will fail. Remove or guard it before merging.
