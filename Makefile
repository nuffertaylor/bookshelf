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
	DOCKER_HOST=unix://$(HOME)/.colima/default/docker.sock \
	  AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
	  sam local start-api --template infra/template.yaml

test:
	pytest tests/

lint:
	ruff check .

deploy:
	cp local-dev/layer-requirements.txt src/requirements.txt
	DOCKER_HOST=unix://$(HOME)/.colima/default/docker.sock \
	  sam build --use-container --template infra/template.yaml
	rm -f src/requirements.txt
	sam deploy \
		--parameter-overrides \
		  DatabaseUrl="{{resolve:ssm:/bookshelf/database_url}}" \
		  CertSecretArn="{{resolve:ssm:/bookshelf/cert_secret_arn}}" \
		  SkipSslCert=""
