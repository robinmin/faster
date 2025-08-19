# Gemini Code Assistant Context

## Project Overview

This is a Python project built using the [FastAPI](https://fastapi.tiangolo.com/) framework. It is designed to be a high-performance web service.

Key technologies used:
- **FastAPI:** For building the API.
- **SQLModel:** For database interaction, providing a blend of SQLAlchemy and Pydantic.
- **Asyncpg:** An asynchronous PostgreSQL driver.
- **Supabase:** Likely used for authentication, database, or other backend services.
- **Uvicorn:** As the ASGI server to run the application.

The project uses `uv` for dependency management, as indicated by the `uv.lock` file.

## Building and Running

### 1. Install Dependencies

To install the necessary dependencies, run the following command:

```bash
uv pip install -r requirements.txt
```

Or, if you have `uv` installed, you can sync with the `pyproject.toml`:

```bash
uv pip sync
```

To install development dependencies:

```bash
uv pip install -r requirements-dev.txt
```

### 2. Running the Application

To run the application locally, use `uvicorn`:

```bash
uvicorn main:app --reload
```
**Note:** This command assumes the FastAPI instance is named `app` in `main.py`. This may need to be adjusted.

### 3. Running Tests

To run the test suite, use `pytest`:

```bash
pytest
```

## Development Conventions

- **Linting:** The project uses `ruff` for code linting and formatting.
- **Testing:** The project uses `pytest` for unit and integration testing. The presence of `pytest-asyncio` suggests that the project has asynchronous tests.
