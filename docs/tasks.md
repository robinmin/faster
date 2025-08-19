# Project: Faster -- a Python project starter that provides a foundation for building high-performance web services. I hope it can help you build your next project `faster`. Happy coding!

##  Major Objectives & features
### Core Architecture & Tooling
- A modern, high-performance API using FastAPI and Python.
- A professional toolchain with `uv` for package management, `ruff` for code quality, and a `Makefile` for automation.
- Comprehensive Testing  with `pytest` for testing, `coverage` for code coverage.
- SQLModel for ORM, Alembic for database migrations.
- `Redis` as a cache and `Celery` for background tasks.
- Adapter layer for deploying to `Cloudflare Workers` and `Docker compose` based VPS.
- Structured Error Handling & Logging: Go beyond FastAPI's default error messages. Implement a centralized system to handle exceptions gracefully, log them for debugging, and provide clear, consistent error responses to your users.

### Folder structure & naming conventions for modules and files:
The whole project is composed of multiple modules, each module is a sub folder at least with the following files(except utilities and tests):
- __init__.py: This file is required for Python to recognize the directory as a Python package.
- schemas.py: Contains the data schemas for both the database and the API.
- services.py: Contains the business logic and services for the application.
- routes.py: Contains the API definitions

### Deployment & Scalability
- A portable Docker setup (`Dockerfile` and `docker-compose.yml`) ready for platforms like Dokploy.
- An adapter pattern architecture, making the app runnable on both traditional servers and serverless platforms like Cloudflare Workers.

### Module Events: `Celery` + `Redis` based pub/sub machnism to handle events asynchronously.

### Module User: Authentication & User Management
- A full-featured authentication system powered by Supabase Auth.
- Support for Email/Password, OAuth (Google & GitHub), and Email OTP ("Magic Link").
- A clean abstraction layer to decouple our app from Supabase, making it easier to maintain and adapt in the future.
- trigger relevants events to other modules via a pub/sub mechanism.

### Module Payments:
- A complete payment processing system using Stripe.
- Handling for both one-time payments (Payment Intents) and recurring subscription billing.
- A secure webhook endpoint to reliably handle real-time events from Stripe, like successful payments and failures.
- trigger relevants events to other modules via a pub/sub mechanism.

### Module Subscriptions
- A full subscription management lifecycle, including endpoints to view status and cancel plans.
- trigger relevants events to other modules via a pub/sub mechanism.

## Task Breakdown
### Phase 1: Core Architecture & Tooling
- [x] 1.0 Setup Core Project Structure
  - [x] 1.0.1 Initialize project with `uv` and `git`.
  - [x] 1.0.2 Create `pyproject.toml` with FastAPI, uvicorn.
  - [x] 1.0.3 Create `main.py` with a basic FastAPI app instance.
  - [x] 1.0.4 Set up `ruff` for linting and formatting.
  - [x] 1.0.5 Create a `Makefile` for common commands (run, test, lint, format, lint, autofix, help).
- [ ] 1.1 Database Setup
  - [x] 1.1.1 Add `sqlmodel` and `alembic` to dependencies.
  - [x] 1.1.2 Configure Alembic for database migrations.
  - [ ] 1.1.3 Implement initial database connection logic with SQLModel.
- [ ] 1.2 Caching & Background Tasks
  - [ ] 1.2.1 Add `redis` and `celery` to dependencies.
  - [ ] 1.2.2 Configure Celery to use Redis as a broker.
  - [ ] 1.2.3 Set up a basic Celery task for testing.
- [ ] 1.3 Error Handling & Logging
  - [ ] 1.3.1 Design a structured error response format.
  - [ ] 1.3.2 Implement a centralized exception handler middleware.
  - [ ] 1.3.3 Configure structured logging (e.g., using `structlog`).
- [ ] 1.4 Testing Setup
  - [ ] 1.4.1 Add `pytest`, `pytest-asyncio`, `coverage` to dev dependencies.
  - [ ] 1.4.2 Configure pytest in `pyproject.toml`.
  - [ ] 1.4.3 Create initial test structure in `tests/`.

### Phase 2: Folder Structure & Conventions
- [ ] 2.0 Establish Module Structure
  - [ ] 2.0.1 Create a `core` or `app` directory for modules.
  - [ ] 2.0.2 Define a template for new modules (`__init__.py`, `schemas.py`, `services.py`, `routes.py`).
  - [ ] 2.0.3 Document the folder structure in `README.md`.

### Phase 3: Module Implementation
- [ ] 3.1 Module: Events (Pub/Sub)
  - [ ] 3.1.1 Design the event schema (event name, payload).
  - [ ] 3.1.2 Implement a Celery-based event publisher service.
  - [ ] 3.1.3 Implement a mechanism for modules to subscribe to events.
- [ ] 3.2 Module: User
  - [ ] 3.2.1 Create the `user` module folder structure.
  - [ ] 3.2.2 Define user schemas in `user/schemas.py`.
  - [ ] 3.2.3 Implement Supabase Auth abstraction layer in `user/services.py`.
  - [ ] 3.2.4 Create routes in `user/routes.py` for user profile management.
  - [ ] 3.2.5 Publish user-related events (e.g., `user.created`).
- [ ] 3.3 Module: Payments
  - [ ] 3.3.1 Create the `payments` module folder structure.
  - [ ] 3.3.2 Define payment schemas in `payments/schemas.py`.
  - [ ] 3.3.3 Implement Stripe client and service layer in `payments/services.py`.
  - [ ] 3.3.4 Create API endpoints for one-time payments and subscriptions.
  - [ ] 3.3.5 Implement a secure Stripe webhook endpoint.
  - [ ] 3.3.6 Publish payment-related events (e.g., `payment.succeeded`).
- [ ] 3.4 Module: Subscriptions
  - [ ] 3.4.1 Create the `subscriptions` module folder structure.
  - [ ] 3.4.2 Define subscription schemas in `subscriptions/schemas.py`.
  - [ ] 3.4.3 Implement service logic to manage subscription lifecycle.
  - [ ] 3.4.4 Create API endpoints for subscription management.
  - [ ] 3.4.5 Subscribe to payment events to update subscription status.
  - [ ] 3.4.6 Publish subscription-related events (e.g., `subscription.cancelled`).

### Phase 4: Deployment & Scalability
- [ ] 4.0 Dockerization
  - [ ] 4.0.1 Create a multi-stage `Dockerfile` for production.
  - [ ] 4.0.2 Create `docker-compose.yml` for local development.
  - [ ] 4.0.3 Create a production-ready `docker-compose.prod.yml`.
- [ ] 4.1 Cloudflare Workers Adapter
  - [ ] 4.1.1 Design the adapter to bridge ASGI and Cloudflare Workers.
  - [ ] 4.1.2 Implement the adapter layer.
  - [ ] 4.1.3 Create a separate build process for the Worker deployment.

### Phase 5: Finalization
- [ ] 5.0 Finalize Documentation
  - [ ] 5.0.1 Update `README.md` with complete setup and deployment instructions.
  - [ ] 5.0.2 Generate API documentation.
  - [ ] 5.0.3 Add architectural diagrams to the `docs/` folder.
- [ ] 5.1 Continuous Integration
  - [ ] 5.1.1 Set up a GitHub Actions workflow to run linting and tests.
