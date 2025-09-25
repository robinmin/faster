# Stage 1: Build dependencies with uv
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS builder

WORKDIR /app

# Install system dependencies (minimal for SQLite)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    make \
    python3-dev \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install Python dependencies using uv (frozen to lock file for reproducibility)
RUN uv sync --locked --no-dev --no-install-project

# ---

# Stage 2: Production image
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS runtime

WORKDIR /app

# Install system dependencies (minimal for SQLite)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    make \
    python3-dev \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

# Copy installed dependencies from builder stage
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy project code (filtered by .dockerignore)
COPY --chown=appuser:appuser . .

# Create data directory for SQLite database
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# Switch to non-root user
USER appuser

# Activate virtual environment and set basic environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

# Note: All other environment variables are now configured via .env files

# Expose port
EXPOSE 8000

# Health check endpoint (assuming /health endpoint exists in your FastAPI app)
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application with Gunicorn and Uvicorn workers (recommended for production)
CMD ["python", "-m", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "4", "main:app"]
