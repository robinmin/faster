.PHONY: help run redis-start test test-e2e test-e2e-manual test-e2e-setup test-e2e-clean lint format autofix db-migrate db-upgrade db-downgrade db-version supabase-start supabase-stop clean

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

clean: ## Clean up build artifacts and cached files
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "*.pyo" -delete 2>/dev/null || true
	@rm -rf build logs .mypy_cache .pytest_cache .ruff_cache .coverage

lock: ## Update the lock file
	uv lock --upgrade
	uv pip compile pyproject.toml -o requirements.txt

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
