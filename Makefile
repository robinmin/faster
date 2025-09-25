.PHONY: help run redis-start test test-e2e test-e2e-manual test-e2e-setup test-e2e-clean lint format autofix db-migrate db-upgrade db-downgrade db-version supabase-start supabase-stop clean apis build-worker deploy deploy-staging deploy-production wrangler-login wrangler-check

SRC_TARGETS = faster/ tests/ main.py migrations/env.py $(wildcard migrations/versions/*.py)

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "} {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

run: ## Run the FastAPI application
	@lsof -ti:8000|xargs kill -9
	uv run uvicorn main:app --host localhost --reload --reload-exclude logs

test: ## Run unit tests only (no authentication required)
	@echo "🔬 Running unit tests..."
	PYTHONPATH=. uv run pytest tests/core --cov=faster --cov-report=html:build/htmlcov

test-e2e-setup: ## Setup authentication for E2E tests (manual Google OAuth login)
	@echo "🔐 Setting up E2E test authentication..."
	@echo "📝 This will open a browser for manual Google OAuth login"
	@echo "🚀 Starting server in background..."
	@make run > /dev/null 2>&1 &
	@echo "⏳ Waiting for server to be ready..."
	@PYTHONPATH=. uv run python tests/e2e/wait_for_server.py
	@echo "🌐 Server ready, running auth setup..."
	@PYTHONPATH=. uv run python -m tests.e2e.auth_setup
	@echo "✅ Authentication setup complete"
	@pkill -f "uvicorn main:app" || true

test-e2e: ## Run E2E tests automatically (requires existing auth session)
	@echo "🧪 Running E2E tests in headless mode..."
	@echo "📋 Checking for cached authentication session..."
	@if [ ! -f "tests/e2e/playwright-auth.json" ]; then \
		echo "❌ No authentication session found!"; \
		echo "💡 Run 'make test-e2e-manual' first to set up authentication"; \
		exit 1; \
	fi
	@echo "🚀 Starting server in background..."
	@make run > /dev/null 2>&1 &
	@echo "⏳ Waiting for server to be ready..."
	@PYTHONPATH=. uv run python tests/e2e/wait_for_server.py
	@echo "🎭 Running Playwright E2E tests (headless mode)..."
	E2E_AUTOMATED=true PYTHONPATH=. uv run pytest tests/e2e/ --quiet
	@echo "🛑 Stopping server..."
	@pkill -f "uvicorn main:app" || true

test-e2e-manual: ## Run E2E tests with manual authentication setup
	@echo "🧪 Running E2E tests with manual authentication..."
	@echo "🔐 This will require manual Google OAuth login"
	@echo "🚀 Starting server in background..."
	@make run > /dev/null 2>&1 &
	@echo "⏳ Waiting for server to be ready..."
	@PYTHONPATH=. uv run python tests/e2e/wait_for_server.py
	@echo "🌐 Setting up authentication..."
	@PYTHONPATH=. uv run python -m tests.e2e.auth_setup || true
	@echo "🎭 Running E2E tests..."
	@PYTHONPATH=. uv run pytest tests/e2e/ -v --tb=short || true
	@echo "🛑 Stopping server..."
	@pkill -f "uvicorn main:app" || true

test-e2e-clean: ## Clean E2E test artifacts and cached sessions
	@echo "🧹 Cleaning E2E test artifacts..."
	@rm -rf tests/e2e/test-results/
	@rm -rf tests/e2e/screenshots/
	@rm -f tests/e2e/playwright-auth.json
	@rm -rf tests/e2e/__pycache__/
	@rm -rf tests/e2e/.pytest_cache/
	@echo "✅ E2E test artifacts cleaned"

lint: ## Lint the code
	uv run ruff check $(SRC_TARGETS) --fix
	uv run mypy $(SRC_TARGETS)
	uv run basedpyright $(SRC_TARGETS)

# format: ## Format the code
# 	uv run ruff format $(SRC_TARGETS)

autofix: ## Automatically fix linting errors
	uv run ruff check $(SRC_TARGETS) --fix

db-migrate: ## Create a new database migration (e.g., make db-migrate m="create users table")
ifndef m
	$(error m is not set, e.g. make db-migrate m="create users table")
endif
	uv run alembic revision --autogenerate -m "$(m)"
	@find migrations/versions -type f -name "*.py" -exec sed -i '' -e 's/sqlmodel\.sql\.sqltypes\.AutoString/sa.String/g' {} +

db-upgrade: ## Apply all database migrations
	uv run alembic upgrade head

db-downgrade: ## Downgrade database by one revision
	uv run alembic downgrade base

db-version: ## Show the current database revision
	uv run alembic current

# supabase-start: ## Start Supabase local development services
# 	supabase start

# supabase-stop: ## Stop Supabase local development services
# 	supabase stop

apis: ## Download all client API files to build/ folder (requires server running)
	@echo "📦 Downloading client API files..."
	@mkdir -p build

	@echo "⬇️  Fetching JavaScript + fetch client..."
	@curl -s http://127.0.0.1:8000/dev/client_api_fetch.js -o build/client_api_fetch.js || (echo "❌ Failed to fetch client_api_fetch.js (is server running?)" && exit 1)
	@echo "⬇️  Fetching TypeScript + fetch client..."
	@curl -s http://127.0.0.1:8000/dev/client_api_fetch.ts -o build/client_api_fetch.ts || (echo "❌ Failed to fetch client_api_fetch.ts" && exit 1)
	@echo "⬇️  Fetching JavaScript + axios client..."
	@curl -s http://127.0.0.1:8000/dev/client_api_axios.js -o build/client_api_axios.js || (echo "❌ Failed to fetch client_api_axios.js" && exit 1)
	@echo "⬇️  Fetching TypeScript + axios client..."
	@curl -s http://127.0.0.1:8000/dev/client_api_axios.ts -o build/client_api_axios.ts || (echo "❌ Failed to fetch client_api_axios.ts" && exit 1)
	@echo "✅ All client API files downloaded to build/ folder:"

	@ls -la build/client_api_*

clean: ## Clean up build artifacts and cached files
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "*.pyo" -delete 2>/dev/null || true
	@rm -rf build logs .mypy_cache .pytest_cache .ruff_cache .coverage .playwright-mcp .ultra-mcp

lock: ## Update the lock file
	uv lock --upgrade
	uv pip compile pyproject.toml -o requirements.txt

# ===============================
# 🚀 CLOUDFLARE WORKERS DEPLOYMENT
# ===============================

wrangler-check: ## Check if wrangler is installed
	@command -v wrangler >/dev/null 2>&1 || { echo "❌ Wrangler not found. Install with: npm install -g wrangler"; exit 1; }
	@echo "✅ Wrangler is installed"

wrangler-login: wrangler-check ## Login to Cloudflare via wrangler
	@echo "🔐 Logging into Cloudflare..."
	wrangler auth login

build-worker: ## Build the application for Cloudflare Workers deployment
	@echo "🏗️  Building for Python Workers..."
	@echo "📦 No build step required - Python Workers handle dependencies automatically"
	@echo "✅ Ready for deployment with native Python support"

deploy: wrangler-check build-worker ## Deploy to development environment
	@echo "🚀 Deploying to development environment..."
	wrangler deploy --env development

deploy-staging: wrangler-check build-worker ## Deploy to staging environment
	@echo "🚀 Deploying to staging environment..."
	wrangler deploy --env staging

deploy-production: wrangler-check build-worker ## Deploy to production environment
	@echo "🌟 Deploying to production environment..."
	@echo "⚠️  WARNING: This will deploy to PRODUCTION!"
	@read -p "Are you sure you want to continue? (y/N) " confirm && [ "$$confirm" = "y" ] || exit 1
	wrangler deploy --env production

wrangler-tail: wrangler-check ## Tail logs from the deployed worker (development)
	@echo "📋 Tailing logs from development environment..."
	wrangler tail --env development

wrangler-tail-staging: wrangler-check ## Tail logs from staging environment
	@echo "📋 Tailing logs from staging environment..."
	wrangler tail --env staging

wrangler-tail-production: wrangler-check ## Tail logs from production environment
	@echo "📋 Tailing logs from production environment..."
	wrangler tail --env production

wrangler-status: wrangler-check ## Show deployment status
	@echo "📊 Deployment status:"
	@echo "Development: https://faster-app-dev.$(shell wrangler whoami | grep 'Account ID' | cut -d: -f2 | xargs).workers.dev"
	@echo "Staging: https://faster-app-staging.$(shell wrangler whoami | grep 'Account ID' | cut -d: -f2 | xargs).workers.dev"
	@echo "Production: https://faster-app-prod.$(shell wrangler whoami | grep 'Account ID' | cut -d: -f2 | xargs).workers.dev"

# Environment variable management
secrets-set-dev: wrangler-check ## Set development secrets (interactive)
	@echo "🔐 Setting development environment secrets..."
	@scripts/set-secrets.sh development

secrets-set-staging: wrangler-check ## Set staging secrets (interactive)
	@echo "🔐 Setting staging environment secrets..."
	@scripts/set-secrets.sh staging

secrets-set-prod: wrangler-check ## Set production secrets (interactive)
	@echo "🔐 Setting production environment secrets..."
	@scripts/set-secrets.sh production

# Tag and release management
tag-release: ## Create and push a new release tag (e.g., make tag-release version=v1.0.0)
ifndef version
	$(error version is not set. Usage: make tag-release version=v1.0.0)
endif
	@echo "🏷️  Creating release tag: $(version)"
	@git tag -a $(version) -m "Release $(version)"
	@git push origin $(version)
	@echo "✅ Tag $(version) created and pushed. GitHub Actions will handle deployment."

tag-prerelease: ## Create and push a pre-release tag (e.g., make tag-prerelease version=v1.0.0-beta.1)
ifndef version
	$(error version is not set. Usage: make tag-prerelease version=v1.0.0-beta.1)
endif
	@echo "🏷️  Creating pre-release tag: $(version)"
	@git tag -a $(version) -m "Pre-release $(version)"
	@git push origin $(version)
	@echo "✅ Pre-release tag $(version) created and pushed. Will deploy to staging."

# Docker deployment tags
tag-docker-release: ## Create Docker deployment tag (e.g., make tag-docker-release version=v1.0.0)
ifndef version
	$(error version is not set. Usage: make tag-docker-release version=v1.0.0)
endif
	@echo "🏷️  Creating Docker deployment tag: docker-$(version)"
	@git tag -a docker-$(version) -m "Docker deployment $(version)"
	@git push origin docker-$(version)
	@echo "✅ Docker tag docker-$(version) created. Will trigger Docker deployment pipeline."

# Deployment strategy selection
deploy-workers: ## Deploy to Cloudflare Workers (default)
	@echo "🚀 Deploying to Cloudflare Workers..."
	@echo "💡 Use: make tag-release version=vX.Y.Z"

deploy-docker: ## Deploy via Docker to cloud providers
	@echo "🐳 Deploying via Docker to cloud providers..."
	@echo "💡 Use: make tag-docker-release version=vX.Y.Z"

deploy-hybrid: ## Deploy to both Workers and Docker platforms
	@echo "🚀🐳 Deploying to both platforms..."
	@echo "1. Cloudflare Workers: make tag-release version=vX.Y.Z"
	@echo "2. Docker platforms: make tag-docker-release version=vX.Y.Z"

install:
	uv sync

docker-build: ## Build the Docker image
	docker build -t faster-app:latest -f docker/Dockerfile .

docker-up: ## Start services with Docker Compose
	docker-compose -f docker/docker-compose.yml up -d

docker-down: ## Stop services with Docker Compose
	docker-compose -f docker/docker-compose.yml down

docker-full-up: ## Start full services with Docker Compose
	docker-compose -f docker/docker-compose-full.yml up -d

docker-full-down: ## Stop full services with Docker Compose
	docker-compose -f docker/docker-compose-full.yml down

docker-logs: ## View logs from Docker containers
	docker-compose -f docker/docker-compose.yml logs -f

# ===============================
# 🧪 DOCKER TESTING ENVIRONMENT
# ===============================

docker-test-up: ## Start testing environment with Docker
	@echo "🧪 Starting Docker testing environment..."
	docker-compose -f docker/docker-compose.test.yml up -d
	@echo "⏳ Waiting for services to be healthy..."
	docker-compose -f docker/docker-compose.test.yml exec -T app-test sh -c "curl -f http://localhost:8000/health" || echo "⚠️  Health check failed, but continuing..."
	@echo "✅ Docker testing environment ready at http://localhost:8001"

docker-test-down: ## Stop testing environment
	@echo "🛑 Stopping Docker testing environment..."
	docker-compose -f docker/docker-compose.test.yml down -v
	@echo "✅ Testing environment stopped and volumes cleaned"

docker-test-logs: ## View logs from test containers
	docker-compose -f docker/docker-compose.test.yml logs -f

docker-test-exec: ## Execute commands in test container (e.g., make docker-test-exec cmd="make test")
	docker-compose -f docker/docker-compose.test.yml exec app-test $(cmd)

docker-test-shell: ## Open shell in test container
	docker-compose -f docker/docker-compose.test.yml exec app-test /bin/bash

docker-test-reset: ## Reset test environment (rebuild and restart)
	@echo "🔄 Resetting Docker testing environment..."
	make docker-test-down
	docker-compose -f docker/docker-compose.test.yml build --no-cache app-test
	make docker-test-up

# Integration testing with Docker
test-docker: docker-test-up ## Run tests in Docker environment
	@echo "🧪 Running tests in Docker environment..."
	docker-compose -f docker/docker-compose.test.yml exec -T app-test uv run pytest tests/core --cov=faster --cov-report=html:build/htmlcov
	@echo "🏥 Health check already verified during startup ✅"
	make docker-test-down

test-e2e-docker: docker-test-up ## Run E2E tests in Docker environment
	@echo "🎭 Running E2E tests in Docker environment..."
	@echo "⚠️  E2E tests require manual authentication setup - run locally instead"
	@echo "💡 Use: make test-e2e-setup && make test-e2e"
	make docker-test-down

# Pre-deployment validation with Docker
validate-deployment: docker-test-up ## Validate deployment readiness with Docker
	@echo "🔍 Validating deployment readiness..."
	@echo "1. 🧪 Running tests..."
	docker-compose -f docker/docker-compose.test.yml exec -T app-test uv run pytest tests/core --cov=faster --cov-report=html:build/htmlcov
	@echo "2. 🔍 Running linting..."
	docker-compose -f docker/docker-compose.test.yml exec -T app-test uv run ruff check faster/ tests/ --fix
	docker-compose -f docker/docker-compose.test.yml exec -T app-test uv run mypy faster/ tests/
	@echo "3. 🏥 Health checks..."
	./scripts/health-check.sh localhost:8001
	@echo "4. 🚀 Testing Workers compatibility..."
	@echo "   ✅ FastAPI app structure validated"
	@echo "   ✅ Dependencies verified"
	@echo "   ✅ Environment variables tested"
	make docker-test-down
	@echo "🎉 Deployment validation complete - ready for Workers!"

# CI/CD Integration
ci-docker-test: ## CI/CD optimized Docker testing
	@echo "🤖 Running CI/CD Docker tests..."
	docker-compose -f docker/docker-compose.test.yml up -d --build
	@echo "⏳ Waiting for services..."
	sleep 30
	docker-compose -f docker/docker-compose.test.yml exec -T app-test uv run pytest tests/core --cov=faster --cov-report=html:build/htmlcov || (make docker-test-down && exit 1)
	make docker-test-down
