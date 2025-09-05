# AGENTS.md

## Project Overview
Faster is a comprehensive web framework that provides a solid foundation for building scalable web applications. It includes pre-configured components for database management, Redis integration, authentication, logging, and more, allowing developers to focus on business logic rather than infrastructure setup.

## Key Features
- **FastAPI Core**: Built on top of FastAPI for high performance and async support
- **Database Integration**: SQLModel/SQLAlchemy with connection pooling and migration support
- **Redis Management**: Multi-provider Redis support with pub/sub capabilities
- **Authentication**: JWT-based authentication system
- **Configuration Management**: Environment-based configuration with Pydantic Settings
- **Logging**: Structured logging with multiple output formats
- **Error Handling**: Comprehensive exception handling mechanisms
- **Testing**: Ready-to-use test setup with pytest
- **Deployment Ready**: Production-ready server configuration

## Core Tasks
This project uses 'make' tool for managing tasks and workflows. It provides the task list via command `make help`.

## Project Coding Rules & Principles

### General Principles
- Single responsibility per module
- Thin repositories (only data access)
- Thin routers (only endpoint definitions)
- Business logic in services only
- External service access through dedicated layers
- Follow established patterns in the codebase
- Use type hints everywhere (strict typing).
- Prefer async/await for I/O-bound operations.

### Module Responsibility Structure (DRP)
- models.py: Define non-database entities only (no business logic)
- schemas.py: Define database entities only (no business logic)
- repositories.py: Database access layer only (no business logic)
- services.py: Business logic combining repositories and external services
- routers.py: RESTful API endpoints only
- middlewares.py: Middleware logic only
- utilities.py: Utility functions only

### Database Access Patterns  (majorly for repositories.py)
- Use QueryBuilder/DeleteBuilder/UpdateBuilder (qb, db, ub) exclusively
- Never use raw SQLAlchemy/SQLModel queries
- Always try to use `get_txn()` for database sessions to write data, simple queries can also use `get_session()` for non-transactional operations.
- No hard deletes - only soft deletes (in_used=0)
- Follow existing query patterns in the codebase

### Data Schema definition (for schemas.py)
- Use 'SQLModel' as the first priority, then can fallback to SQLAlchemy.
- Member variable names should be separated with DB field names
- Naming conventions for DB fields:
    - Snake_case in uppercase letter, use underscores to separate words
    - Always start with data type prefix: C_: for string, N_: for number, B_: for boolean, D_: for date/timestamp
    - avoid to use text field type as possible
- all classes should be inherited from 'MyBase'
for example:
```python
category: str = Field(max_length=64, sa_column_kwargs={"name": "C_CATEGORY"})
```

### Logging Standards
- Necessary logging only: Log errors, warnings, and important events
- Avoid excessive logging throughout normal operation flows
- Use appropriate log levels: error, warning, info, debug (sparingly)
- Include context in log messages for troubleshooting

### Authentication Flow
- All external auth service access through dedicated proxy layer
- All database access through repositories
- Business logic in services
- Endpoints in routers

### Upsert Patterns
- Single unique records: Query and update if exists, otherwise insert
- Collection records: Soft delete all existing, then insert new collection
- Always use soft delete (in_used=0) instead of hard delete

### Code Quality Standards
- All source code must pass: ruff, mypy, and pyright checks
- No `# type: ignore` unless absolutely unavoidable
- Follow PEP 8 and project-specific style guides
- Write type hints for all functions and variables

### Testing Practices (TDD)
- Write tests first when implementing new features
- Follow existing test patterns and conventions
- Maintain high test coverage for business logic
- All tests must pass before committing changes

## Testing Guidelines
- Framework: pytest
- Coverage: Aim for 80%+
- Tests go under tests/, mirroring app/ structure.
- Use pytest fixtures for DB setup/teardown.
- Mock external services (e.g., APIs, storage).
