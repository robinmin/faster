# Stage 1: Build dependencies with uv
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS builder

WORKDIR /app

# Install system dependencies required for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install Python dependencies using uv (frozen to lock file for reproducibility)
RUN uv sync --locked --no-dev --no-install-project

# ---

# Stage 2: Production image
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS runtime

WORKDIR /app

# Install system dependencies required for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

# Copy installed dependencies from builder stage
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy project code (filtered by .dockerignore)
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Activate virtual environment and set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000 \
    DATABASE_URL="sqlite+aiosqlite:///./test.db" \
    REDIS_URL="redis://localhost:6379" \
    REDIS_PASSWORD="" \
    CELERY_BROKER_URL="redis://localhost:6379" \
    CELERY_RESULT_BACKEND="redis://localhost:6379" \
    SUPABASE_URL="http://localhost:54321" \
    SUPABASE_ANON_KEY="your-anon-key" \
    SUPABASE_SERVICE_KEY="your-service-key" \
    SUPABASE_JWKS_URL="http://localhost:54321/auth/v1/.well-known/jwks.json" \
    STRIPE_SECRET_KEY="your-stripe-secret-key" \
    STRIPE_WEBHOOK_SECRET="your-stripe-webhook-secret" \
    STRIPE_PUBLISHABLE_KEY="your-stripe-publishable-key" \
    JWT_SECRET_KEY="your-jwt-secret-key"

# Expose port
EXPOSE 8000

# Health check endpoint (assuming /health endpoint exists in your FastAPI app)
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application with Gunicorn and Uvicorn workers (recommended for production)
CMD ["python", "-m", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "4", "main:app"]