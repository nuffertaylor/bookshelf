dev:
	docker compose -f local-dev/docker-compose.yml up -d

# Install Linux-compiled packages into src/ so SAM local uses the right binaries.
# Must run before `make local` on a fresh checkout, or after changing layer-requirements.txt.
layer-deps:
	DOCKER_HOST=unix://$(HOME)/.colima/default/docker.sock \
	  docker run --rm \
	    -v $(CURDIR)/src:/opt/layer \
	    python:3.12-slim \
	    pip install -r /opt/layer/../local-dev/layer-requirements.txt -t /opt/layer/ -q

local: layer-deps
	sam build --template infra/template.yaml
	@# '@' keeps make from echoing the command, which can contain HARDCOVER_CLIENT_SECRET.
	@# Export these in your shell first (never put the secret in a tracked file):
	@#   KMS_KEY_ID (LocalStack key id), HARDCOVER_CLIENT_ID, HARDCOVER_CLIENT_SECRET
	@DOCKER_HOST=unix://$(HOME)/.colima/default/docker.sock \
	  AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
	  sam local start-api \
	    --parameter-overrides AwsEndpointUrl="http://host.docker.internal:4566" \
	      KmsEndpointUrl="http://host.docker.internal:4566" \
	      $(if $(KMS_KEY_ID),KmsKeyId="$(KMS_KEY_ID)") \
	      $(if $(HARDCOVER_CLIENT_ID),HardcoverClientId="$(HARDCOVER_CLIENT_ID)") \
	      $(if $(HARDCOVER_CLIENT_SECRET),HardcoverClientSecret="$(HARDCOVER_CLIENT_SECRET)") \
	    --port 3001

test:
	uv run pytest tests/

lint:
	uv run ruff check .

# Use the Colima socket only when it exists (macOS with Colima); Docker Desktop and CI use the default.
DEPLOY_DOCKER_HOST := $(if $(wildcard $(HOME)/.colima/default/docker.sock),DOCKER_HOST=unix://$(HOME)/.colima/default/docker.sock)

# Needs AWS credentials in the environment (CI assumes a role; locally use your profile).
# See docs/deploy.md for the parameters this reads and the one-time AWS setup.
deploy:
	cp local-dev/layer-requirements.txt src/requirements.txt
	$(DEPLOY_DOCKER_HOST) sam build --use-container --template infra/template.yaml
	rm -f src/requirements.txt
	sam deploy \
		--stack-name bookshelf \
		--region us-east-1 \
		--resolve-s3 \
		--capabilities CAPABILITY_IAM \
		--no-confirm-changeset \
		--no-fail-on-empty-changeset \
		--parameter-overrides \
		  Prefix="v2-" \
		  DatabaseUrl="{{resolve:ssm:/bookshelf/database_url}}" \
		  CertSecretArn="{{resolve:ssm:/bookshelf/cert_secret_arn}}" \
		  SkipSslCert=false \
		  HardcoverClientId="{{resolve:ssm:/bookshelf/hardcover_client_id}}" \
		  HardcoverSecretArn="{{resolve:ssm:/bookshelf/hardcover_secret_arn}}" \
		  HardcoverRedirectUri="https://www.mybookshelf.dev/oauth/callback" \
		  KmsKeyId="{{resolve:ssm:/bookshelf/kms_key_id}}"
