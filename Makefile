.PHONY: help run redis-start test lint format autofix db-migrate db-upgrade db-downgrade db-version supabase-start supabase-stop clean

SRC_TARGETS = faster/ tests/ main.py migrations/env.py $(wildcard migrations/versions/*.py)

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "} {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

run: ## Run the FastAPI application
	uv run uvicorn main:app --reload --reload-exclude logs

test: ## Run tests
	PYTHONPATH=. uv run pytest --cov=faster --cov-report=html:build/htmlcov

lint: autofix ## Lint the code
	uv run ruff check $(SRC_TARGETS)
	uv run mypy $(SRC_TARGETS)

format: ## Format the code
	ruff format $(SRC_TARGETS)

autofix: format ## Automatically fix linting errors
	ruff check $(SRC_TARGETS) --fix

db-migrate: ## Create a new database migration (e.g., make db-migrate m="create users table")
ifndef m
	$(error m is not set, e.g. make db-migrate m="create users table")
endif
	uv run alembic revision --autogenerate -m "$(m)"

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
	@rm -rf __pycache__ \
		$(find . -depth -name "__pycache__") \
		$(find . -depth -name "*.pyc") \
		$(find . -depth -name "*.pyo") \
		build \
		logs/app.log \
		.mypy_cache \
		.mypy_cache \
		.pytest_cache \
		.ruff_cache \
		.coverage

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
