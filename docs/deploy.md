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

## 2. Production DB settings and certificate

The existing `loginRegister` lambda holds the connection string:

```powershell
aws lambda get-function-configuration --function-name loginRegister --query "Environment.Variables"
```

It has a `DATABASE_URL` and nothing else. There is no `CERT_SECRET_ARN` because the old lambdas bundle the CockroachDB certificate (`root.crt`) inside their zip. The new code reads it from Secrets Manager, so you need to create that secret.

**a. Create the secret** from `root.crt`. If you already have the file, put it in the repo root (`*.crt` is gitignored, so it won't be committed), and run this from there:

```powershell
Test-Path .\root.crt
aws secretsmanager create-secret --name bookshelf/db-cert --secret-string file://root.crt
```

`Test-Path` must print `True`. Note the `ARN` in the output of the second command.

If you don't have the file, it's inside the live lambda's zip (`aws lambda get-function --function-name loginRegister --query Code.Location --output text` prints a download URL), or you can download the CA cert from the CockroachDB Cloud console (cluster, Connect dialog).

**b. Store both values as SSM parameters**, replacing the bracketed values (without the brackets). `[DATABASE_URL]` is the full string from the first command:

```powershell
aws ssm put-parameter --name /bookshelf/database_url --type String --value "[DATABASE_URL]"
aws ssm put-parameter --name /bookshelf/cert_secret_arn --type String --value "[secret ARN]"
```

The database URL contains a password and ends up in the lambdas' environment variables regardless (as it does today), so this adds no new exposure.


### Hardcover prerequisites (this branch only)

On this branch `make deploy` also passes the Hardcover parameters, so these SSM parameters must exist **before** the first deploy (including the automatic one after merging to `master`), or CloudFormation fails to resolve them:

- `/bookshelf/hardcover_client_id`
- `/bookshelf/hardcover_secret_arn` (ARN of the Secrets Manager secret holding the client secret)
- `/bookshelf/kms_key_id` (KMS key used to encrypt stored Hardcover tokens)

`plans/04-hardcover-manual-steps.md` (Part C) has the commands to create the KMS key, the secret and these parameters, and Part D covers the production database migration, which must also run **before** the new code is deployed. Also create the KMS key and secret in the same account and region as the stack.

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
    SkipSslCert="false"
```

(`SkipSslCert="false"` means "use the cert". SAM rejects an empty value, and the app only skips the cert for `true`, `1` or `yes`.)

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

## Automatic deploys from GitHub (push to `master`)

The `deploy` job in `.github/workflows/ci.yml` runs `make deploy` after the tests pass on every push to `master`. It updates the same `bookshelf` stack as above, and does nothing if nothing changed. It signs in to AWS by assuming a role through OIDC, so there are no AWS keys stored in GitHub. The role can only be assumed by runs on the `master` branch of `nuffertaylor/bookshelf`.

Do the first manual deploy (steps 1 to 7) before enabling this: the job updates an existing stack and reads the `/bookshelf/...` SSM parameters you created in step 2. One-time setup:

**a. Create the role.** From the repo root in PowerShell:

```powershell
aws cloudformation deploy `
  --template-file infra\github-deploy-role.yaml `
  --stack-name bookshelf-github-deploy `
  --capabilities CAPABILITY_NAMED_IAM `
  --region us-east-1
```

If this fails with "Provider with url https://token.actions.githubusercontent.com already exists", your account already has the GitHub OIDC provider. Find its ARN with `aws iam list-open-id-connect-providers`, then re-run the command above with `--parameter-overrides ExistingOidcProviderArn=<that arn>` added.

**b. Read the role ARN:**

```powershell
aws cloudformation describe-stacks --stack-name bookshelf-github-deploy --query "Stacks[0].Outputs" --output table
```

**c. Add it to GitHub.** In the repo on github.com: Settings, then Secrets and variables, then Actions, then New repository secret. Name it `AWS_DEPLOY_ROLE_ARN` and paste the ARN.

**d. Try it.** Merge to `master` (or push a small change), then watch the Actions tab. The `deploy` job takes a few minutes because it builds in Docker. If it fails, the log shows the CloudFormation or permission error; the role's permissions are in `infra/github-deploy-role.yaml` and are easy to extend.

Notes:
- `make deploy` also works locally (Mac or CI) if your shell has AWS credentials, for example `AWS_PROFILE=... make deploy`.
- The deploy always uses prefix `v2-`. When you later drop the old functions and the prefix, change `Prefix` in the `Makefile`.
- If the role template's stack name or the repo moves, change the `GitHubRepo` / `StackName` parameters.
- Deploys only run on pushes to `master`, not on pull requests or other branches.

## Rollback and cleanup

- **Rollback:** point `REACT_APP_API_URL` back at `https://vi64h2xk34.execute-api.us-east-1.amazonaws.com/alpha/`.
- **Retire the old setup** once you're confident: delete the old functions and the old API. Deleting the stack (`aws cloudformation delete-stack --stack-name bookshelf`) removes only the `v2-` resources.
- **Later renaming:** a stack with an empty `Prefix` collides with the live function names, so drop the prefix only after the old functions are deleted.
