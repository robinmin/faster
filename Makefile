# ===============================
# 🚀 FASTER - FastAPI Development Makefile
# ===============================

.PHONY: help install setup dev test test-e2e test-e2e-auth test-e2e-check lint db-migrate db-upgrade db-reset docker-up docker-down docker-status docker-test ci-docker-test deploy deploy-staging deploy-prod deploy-prod-ci clean

# Configuration
SRC_TARGETS = faster/ tests/ main.py migrations/env.py $(wildcard migrations/versions/*.py)
DOCKER_COMPOSE = docker-compose -f docker/docker-compose.yml
DOCKER_TEST_COMPOSE = docker-compose -f docker/docker-compose.test.yml

# ===============================
# 📋 HELP & INFORMATION
# ===============================

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "} {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

# ===============================
# 📦 ENVIRONMENT PREPARATION
# ===============================

install: ## Install all dependencies and setup environment
	@if [ -n "$$VIRTUAL_ENV" ]; then deactivate 2>/dev/null || true; fi
	@rm -rf .venv >/dev/null 2>&1 || true
	@uv venv .venv --python 3.10
	@uv sync >/dev/null 2>&1 || (echo "❌ Failed to install Python dependencies" && exit 1)
	@if ! command -v wrangler >/dev/null 2>&1; then \
		npm install -g wrangler >/dev/null 2>&1 || (echo "❌ Failed to install wrangler" && exit 1); \
	fi
	@echo "✅ Environment ready! Run 'source .venv/bin/activate' to activate"

setup: install ## Complete project setup (alias for install)

clean: ## Clean build artifacts and cache files
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "*.pyo" -delete 2>/dev/null || true
	@rm -rf build logs .mypy_cache .pytest_cache .ruff_cache .playwright-mcp .coverage 2>/dev/null || true
	@rm -rf tests/e2e/test-results tests/e2e/screenshots tests/e2e/__pycache__ 2>/dev/null || true
	@echo "✅ Cleaned build artifacts and cache files"

lock: ## Update dependency lock files
	@uv lock --upgrade >/dev/null 2>&1 || (echo "❌ Failed to update lock file" && exit 1)
	@uv pip compile pyproject.toml -o requirements.txt >/dev/null 2>&1 || true
	@echo "✅ Dependencies locked"

# ===============================
# 🔧 LOCAL DEVELOPMENT
# ===============================

dev: ## Start development server (kills existing and starts fresh)
	@lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
	@uv run uvicorn main:app --host localhost --reload --reload-exclude logs

run: dev ## Alias for dev command

apis: ## Download client API files (auto-starts server if needed)
	@mkdir -p build >/dev/null 2>&1
	@if [ $$(lsof -ti:8000 2>/dev/null | wc -l | tr -d ' ') -eq 0 ]; then \
		echo "🚀 Starting server..."; \
		uv run uvicorn main:app --host localhost --reload --reload-exclude logs >/dev/null 2>&1 & \
		sleep 3; \
		STARTED_SERVER=1; \
	else \
		STARTED_SERVER=0; \
	fi; \
	curl -sf http://127.0.0.1:8000/dev/client_api_fetch.js -o build/client_api_fetch.js >/dev/null 2>&1; \
	curl -sf http://127.0.0.1:8000/dev/client_api_fetch.ts -o build/client_api_fetch.ts >/dev/null 2>&1; \
	curl -sf http://127.0.0.1:8000/dev/client_api_axios.js -o build/client_api_axios.js >/dev/null 2>&1; \
	curl -sf http://127.0.0.1:8000/dev/client_api_axios.ts -o build/client_api_axios.ts >/dev/null 2>&1; \
	if [ "$$STARTED_SERVER" -eq 1 ]; then \
		lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true; \
	fi; \
	echo "✅ API clients downloaded"

lint: ## Run all code quality checks
	uv run ruff check $(SRC_TARGETS) --fix
	uv run mypy $(SRC_TARGETS)
	uv run basedpyright $(SRC_TARGETS)

# ===============================
# 🗄️ DATABASE MIGRATION
# ===============================

db-migrate: ## Create new migration (usage: make db-migrate m="description")
ifndef m
	$(error Usage: make db-migrate m="migration description")
endif
	@uv run alembic revision --autogenerate -m "$(m)" || (echo "❌ Migration creation failed" && exit 1)
	@find migrations/versions -type f -name "*.py" -exec sed -i '' -e 's/sqlmodel\.sql\.sqltypes\.AutoString/sa.String/g' {} + 2>/dev/null || true
	@echo "✅ Migration created: $(m)"

db-upgrade: ## Apply all pending migrations
	@uv run alembic upgrade head || (echo "❌ Migration failed" && exit 1)
	@echo "✅ Database upgraded to latest"

db-reset: ## Reset database (downgrade to base then upgrade)
	@uv run alembic downgrade base || (echo "❌ Downgrade failed" && exit 1)
	@uv run alembic upgrade head || (echo "❌ Upgrade failed" && exit 1)
	@echo "✅ Database reset complete"

db-version: ## Show current database version
	@uv run alembic current

# # D1 Database Commands
# d1-create: ## Create D1 databases for all environments
# 	@echo "🗄️ Creating D1 databases..."
# 	@wrangler d1 create faster-app-dev || echo "⚠️  faster-app-dev may already exist"
# 	@wrangler d1 create faster-app-staging || echo "⚠️  faster-app-staging may already exist"
# 	@wrangler d1 create faster-app-prod || echo "⚠️  faster-app-prod may already exist"
# 	@echo "✅ D1 databases created (update wrangler.toml with database IDs)"

# d1-query: ## Execute SQL query on D1 database (usage: make d1-query env=dev query="SELECT COUNT(*) FROM users")
# ifndef env
# 	$(error Usage: make d1-query env=dev query="SELECT * FROM users")
# endif
# ifndef query
# 	$(error Usage: make d1-query env=dev query="SELECT * FROM users")
# endif
# 	@wrangler d1 execute faster-app-$(env) --command="$(query)"

# ===============================
# 🧪 LOCAL TESTING
# ===============================

test: ## Run unit tests with coverage
	@PYTHONPATH=. uv run pytest tests/core --cov=faster --cov-report=html:build/htmlcov -q

test-e2e: ## Run E2E tests (shows output for debugging)
	@echo "🧪 Running E2E tests..."
	@make dev >/dev/null 2>&1 &
	@sleep 3
	@PYTHONPATH=. uv run python tests/e2e/wait_for_server.py >/dev/null 2>&1
	@E2E_AUTOMATED=true PYTHONPATH=. uv run pytest tests/e2e/ -v || \
		(echo "❌ E2E tests failed - check authentication with 'make test-e2e-check'" && pkill -f "uvicorn main:app" 2>/dev/null || true && exit 1)
	@pkill -f "uvicorn main:app" 2>/dev/null || true
	@echo "✅ E2E tests passed"

test-e2e-auth: ## Regenerate E2E authentication credentials
	@echo "🔐 Regenerating E2E authentication credentials..."
	@make dev >/dev/null 2>&1 &
	@sleep 3
	@PYTHONPATH=. uv run python tests/e2e/wait_for_server.py >/dev/null 2>&1
	@PYTHONPATH=. uv run python tests/e2e/regenerate_auth.py
	@pkill -f "uvicorn main:app" 2>/dev/null || true

test-e2e-check: ## Check E2E authentication status
	@PYTHONPATH=. uv run python tests/e2e/regenerate_auth.py --check

# ===============================
# 🐳 DOCKER MANAGEMENT
# ===============================

docker-up: ## Start application with Docker Compose
	@$(DOCKER_COMPOSE) up -d --build

docker-down: ## Stop Docker services
	@$(DOCKER_COMPOSE) down

docker-logs: ## View Docker container logs
	@$(DOCKER_COMPOSE) logs -f

docker-status: ## Show status of project Docker containers and images
	@echo "🐳 Docker Status for FASTER Project"
	@echo ""
	@echo "📦 Project Images:"
	@docker images | grep -E "(docker-app|faster-)" || echo "  No project images found"
	@echo ""
	@echo "🏃 Running Containers:"
	@docker ps --filter "name=faster-" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" || echo "  No project containers running"
	@echo ""
	@echo "💤 All Project Containers (including stopped):"
	@docker ps -a --filter "name=faster-" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" || echo "  No project containers found"
	@echo ""
	@echo "🌐 Docker Networks:"
	@docker network ls | grep -E "(docker_|test-network)" || echo "  No project networks found"
	@echo ""
	@echo "💾 Docker Volumes:"
	@docker volume ls | grep -E "(docker_|test_)" || echo "  No project volumes found"

docker-test: ## Run tests in Docker environment
	@echo "🧪 Running tests in Docker..."
	@$(DOCKER_TEST_COMPOSE) up -d --build || (echo "❌ Failed to start test environment" && exit 1)
	@sleep 5
	@$(DOCKER_TEST_COMPOSE) exec -T app-test uv run pytest tests/core --cov=faster -q || \
		(echo "❌ Docker tests failed" && $(DOCKER_TEST_COMPOSE) down >/dev/null 2>&1 && exit 1)
	@$(DOCKER_TEST_COMPOSE) down >/dev/null 2>&1
	@echo "✅ Docker tests passed"

ci-docker-test: ## CI/CD optimized Docker testing (for GitHub Actions)
	@echo "🤖 Running CI/CD Docker tests..."
	@$(DOCKER_TEST_COMPOSE) up -d --build
	@sleep 10
	@$(DOCKER_TEST_COMPOSE) exec -T app-test uv run pytest tests/core --cov=faster --maxfail=5 -q || \
		(echo "❌ CI Docker tests failed" && $(DOCKER_TEST_COMPOSE) down && exit 1)
	@$(DOCKER_TEST_COMPOSE) down
	@echo "✅ CI Docker tests passed"

# ===============================
# 🚀 DEPLOYMENT
# ===============================

wrangler-login: ## Login to Cloudflare
	@wrangler auth login

wrangler-status: ## Show deployment URLs
	@echo "📊 Deployment URLs:"
	@echo "Development: https://faster-app-dev.$(shell wrangler whoami 2>/dev/null | grep 'Account ID' | cut -d: -f2 | xargs).workers.dev"
	@echo "Staging: https://faster-app-staging.$(shell wrangler whoami 2>/dev/null | grep 'Account ID' | cut -d: -f2 | xargs).workers.dev"
	@echo "Production: https://faster-app-prod.$(shell wrangler whoami 2>/dev/null | grep 'Account ID' | cut -d: -f2 | xargs).workers.dev"

github-status: ## Show GitHub status
	@echo "📊 Github Status:"
	@gh auth status

status: wrangler-status github-status ## Show all necessary status information
	@echo "✅ All status information is up-to-date"

deploy: ## Deploy to development environment
	@echo "🚀 Deploying to development..."
	@wrangler deploy --env development || (echo "❌ Deployment failed" && exit 1)
	@echo "✅ Deployed to development"

deploy-staging: ## Deploy to staging environment
	@echo "🚀 Deploying to staging..."
	@wrangler deploy --env staging || (echo "❌ Deployment failed" && exit 1)
	@echo "✅ Deployed to staging"

deploy-prod: ## Deploy to production (with confirmation)
	@echo "⚠️  WARNING: This will deploy to PRODUCTION!"
	@read -p "Continue? (y/N) " confirm && [ "$$confirm" = "y" ] || (echo "Cancelled" && exit 1)
	@echo "🌟 Deploying to production..."
	@wrangler deploy --env production || (echo "❌ Deployment failed" && exit 1)
	@echo "✅ Deployed to production"

deploy-prod-ci: ## Deploy to production (non-interactive for CI/CD)
	@echo "🌟 Deploying to production (CI/CD mode)..."
	@wrangler deploy --env production || (echo "❌ Deployment failed" && exit 1)
	@echo "✅ Deployed to production"


tag-release: ## Create release tag (usage: make tag-release version=v1.0.0)
ifndef version
	$(error Usage: make tag-release version=v1.0.0)
endif
	@git tag -a $(version) -m "Release $(version)" >/dev/null 2>&1 || (echo "❌ Failed to create tag" && exit 1)
	@git push origin $(version) >/dev/null 2>&1 || (echo "❌ Failed to push tag" && exit 1)
	@echo "✅ Release tag $(version) created and pushed"

# ===============================
# 🧹 MISCELLANEOUS
# ===============================
