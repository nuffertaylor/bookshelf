# Deploying the Bookshelf stack to AWS (Windows / PowerShell)

This creates a CloudFormation stack (`bookshelf`) containing new lambdas named `v2-loginRegister`, `v2-genShelf`, ... and a **new API Gateway** with its own URL. It uses the **production database and the `bookshelf-spines` bucket**. The live, manually deployed lambdas and the old API (`.../alpha/`) are not touched and keep working, so you can switch the frontend over when ready and roll back by switching the URL back.

The `v2-` prefix exists because CloudFormation can't create a function whose name already exists. Once everything runs on the new stack you can delete the old functions and the old API.

Run everything in PowerShell from the repo root, on the `refactor` branch (`git checkout refactor; git pull`).

## 1. Prerequisites

First check what is already installed:

```powershell
aws --version
sam --version
docker --version
```

Any line that prints a version is fine, so skip its install. A line that errors with "not recognized" means the tool is missing, so install only that one:

```powershell
winget install -e --id Amazon.AWSCLI           # if `aws` is missing
winget install -e --id Amazon.SAM-CLI          # if `sam` is missing
winget install -e --id Docker.DockerDesktop    # if `docker` is missing
```

If you installed anything, open a new PowerShell window so it's on your PATH. In the VS Code terminal, a new terminal tab is not enough: quit VS Code completely and reopen it, or the new tools stay "not recognized". Start Docker Desktop and wait for "Engine running", then check that everything works:

```powershell
docker run --rm hello-world
aws sts get-caller-identity
```

If `aws sts get-caller-identity` fails with a credentials error (or you've never configured the CLI on this machine), run `aws configure` (access key, secret, region `us-east-1`) and try again. If it prints an account ID, skip `aws configure`.

The IAM user needs to create CloudFormation stacks, Lambda, API Gateway, IAM roles/policies, S3 (SAM artifacts bucket) and SSM parameters. An admin user is simplest.

## 2. Find the production DB settings

The existing lambdas already hold the values. Read them from one of them:

```powershell
aws lambda get-function-configuration --function-name loginRegister --query "Environment.Variables"
```

Note `DATABASE_URL` and `CERT_SECRET_ARN`. (If `SKIP_SSL_CERT` is set there, tell me; the deploy command changes.)

Store them as SSM parameters, replacing the bracketed values (without the brackets):

```powershell
aws ssm put-parameter --name /bookshelf/database_url --type String --value "[DATABASE_URL]"
aws ssm put-parameter --name /bookshelf/cert_secret_arn --type String --value "[CERT_SECRET_ARN]"
```

The database URL contains a password and ends up in the lambdas' environment variables regardless (as it does today), so this adds no new exposure.

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
  --stack-name bookshelf `
  --region us-east-1 `
  --resolve-s3 `
  --capabilities CAPABILITY_IAM `
  --no-confirm-changeset `
  --parameter-overrides `
    Prefix="v2-" `
    DatabaseUrl="{{resolve:ssm:/bookshelf/database_url}}" `
    CertSecretArn="{{resolve:ssm:/bookshelf/cert_secret_arn}}" `
    SkipSslCert=""
```

(`SkipSslCert=""` means "use the cert".)

When it finishes, read the API URL:

```powershell
aws cloudformation describe-stacks --stack-name bookshelf --query "Stacks[0].Outputs" --output table
```

If the stack ends in `ROLLBACK_COMPLETE`, find the cause with:

```powershell
aws cloudformation describe-stack-events --stack-name bookshelf --query "StackEvents[?contains(ResourceStatus,'FAILED')].[LogicalResourceId,ResourceStatusReason]" --output table
```

then delete the failed stack (`aws cloudformation delete-stack --stack-name bookshelf`) before redeploying. Send me the output and I'll diagnose.

## 5. Smoke test

```powershell
curl.exe "<ApiUrl>leaderboard"
```

It should return JSON (so the database connection works). A 502 means the lambda crashed; read its log:

```powershell
aws logs tail /aws/lambda/v2-leaderboard --since 15m
```

## 6. Point the frontend at it

In `bookshelf-ts-site` (branch `refactor`), create `.env.development.local` containing:

```
REACT_APP_API_URL=<ApiUrl>
```

(keep the trailing slash), then `npm start` and log in and generate a shelf on http://localhost:3000. The browser console and `aws logs tail` will show failures. To go live, set the same value in the production build's `.env.production` and redeploy the site.

## 7. Check API Gateway logging

Requests carry session tokens. Confirm the `Prod` stage has no full request/response body logging (API Gateway console, stage, Logs/Tracing).

## Rollback and cleanup

- **Rollback:** point `REACT_APP_API_URL` back at `https://vi64h2xk34.execute-api.us-east-1.amazonaws.com/alpha/`.
- **Retire the old setup** once you're confident: delete the old functions and the old API. Deleting the stack (`aws cloudformation delete-stack --stack-name bookshelf`) removes only the `v2-` resources.
- **Later renaming:** a stack with an empty `Prefix` collides with the live function names, so drop the prefix only after the old functions are deleted.
- **CI:** the `deploy` job in `.github/workflows/ci.yml` still runs `make deploy` on `master` without AWS secrets and will fail. Remove or guard it before merging.
