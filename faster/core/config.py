from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


###############################################################################
# Define config settings
###############################################################################
class Settings(BaseSettings):
    """Application configuration management, supports environment variables and .env files."""

    # Basic application settings
    app_name: str = Field(default="faster", description="Application name")
    app_version: str = Field(default="0.0.1", description="Application version")
    app_description: str = Field(
        default="A modern and fast Python web framework",
        description="Application description",
    )
    environment: str = Field(default="development", description="Runtime environment")
    api_prefix: str = Field(default="/api/v1", description="API prefix")
    refresh_interval: int = Field(default=300, description="Refresh interval in seconds")

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=4, description="Number of worker processes")
    access_log: bool = Field(default=True, description="Enable access log")
    limit_concurrency: int | None = Field(default=None, description="Concurrency limit")
    limit_max_requests: int | None = Field(default=None, description="Maximum number of requests")
    timeout_keep_alive: int = Field(default=5, description="Keep-alive timeout")
    ssl_keyfile: str | None = Field(default=None, description="Path to SSL key file")
    ssl_certfile: str | None = Field(default=None, description="Path to SSL certificate file")
    ssl_version: int | None = Field(default=None, description="SSL version")
    reload_dirs: list[str] = Field(default=[], description="Directories to watch for reloading")
    reload_includes: list[str] = Field(default=[], description="Files to include for reloading")
    reload_excludes: list[str] = Field(default=[], description="Files to exclude for reloading")
    allowed_hosts: list[str] = Field(default=["*"], description="List of allowed hosts")

    # Database settings
    database_url: str | None = Field(default=None, description="Database connection URL")
    database_pool_size: int = Field(default=20, description="Connection pool size")
    database_max_overflow: int = Field(default=0, description="Maximum overflow connections for the pool")
    database_echo: bool = Field(default=False, description="Enable SQL logging")

    # Redis settings
    redis_provider: str = Field(default="local", description="Redis provider type (e.g., local, upstash, fake)")
    redis_url: str | None = Field(default=None, description="Redis connection URL")
    redis_password: str | None = Field(default=None, description="Redis password for local, and token for Upstash")
    redis_max_connections: int = Field(default=50, description="Maximum number of Redis connections")
    redis_decode_responses: bool = Field(default=True, description="Automatically decode Redis responses")
    redis_enabled: bool = Field(default=True, description="Whether Redis is enabled")

    # Celery settings
    celery_broker_url: str | None = Field(default=None, description="Celery Broker URL")
    celery_result_backend: str | None = Field(default=None, description="Celery result backend")
    celery_task_always_eager: bool = Field(default=False, description="Execute Celery tasks synchronously")

    # Supabase settings
    supabase_url: str | None = Field(default=None, description="Supabase project URL")
    supabase_anon_key: str | None = Field(default=None, description="Supabase anonymous key")
    supabase_service_key: str | None = Field(default=None, description="Supabase service key")
    supabase_jwks_url: str | None = Field(default=None, description="Supabase JWKs URL")
    supabase_audience: str | None = Field(default=None, description="Supabase audience")
    auto_refresh_jwks: bool = Field(default=True, description="Auto refresh JWKs from Supabase")

    # Stripe settings
    stripe_secret_key: str | None = Field(default=None, description="Stripe secret key")
    stripe_webhook_secret: str | None = Field(default=None, description="Stripe webhook secret")
    stripe_publishable_key: str | None = Field(default=None, description="Stripe publishable key")

    # Security settings
    auth_enabled: bool = Field(default=True, description="Enable authentication")
    jwt_secret_key: str | None = Field(default=None, description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiry_minutes: int = Field(default=60, description="JWT expiry time in minutes")

    # CORS settings
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")
    cors_credentials: bool = Field(default=True, description="Allow CORS credentials")
    cors_enabled: bool = Field(default=True, description="Enable CORS")
    cors_allow_methods: list[str] = Field(default=["*"], description="Allowed CORS methods")
    cors_allow_headers: list[str] = Field(
        default=["X-Requested-With", "X-Request-ID"], description="Allowed CORS headers"
    )
    cors_expose_headers: list[str] = Field(default=["X-Request-ID"], description="Exposed CORS headers")
    gzip_enabled: bool = Field(default=True, description="Enable GZip compression")
    gzip_min_size: int = Field(default=1000, description="Minimum size for GZip compression")
    trusted_hosts: list[str] = Field(default=["*"], description="Trusted hosts")

    # Logging settings
    log_level: str = Field(default="INFO", description="Log level")
    log_format: Literal["json", "console"] = Field(default="json", description="Log format")
    log_file: str | None = Field(default=None, description="Path to log file")

    # Deployment Platform Settings
    deployment_platform: Literal["vps", "cloudflare-workers", "auto"] = Field(
        default="auto", description="Target deployment platform"
    )

    # VPS-specific settings
    vps_reverse_proxy: bool = Field(default=False, description="Running behind reverse proxy (Nginx/Apache)")
    vps_static_files_path: str = Field(default="static", description="Static files directory path")
    vps_max_request_size: int = Field(default=16 * 1024 * 1024, description="Maximum request size in bytes")
    vps_enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics endpoint")
    vps_process_manager: Literal["uvicorn", "gunicorn", "hypercorn"] = Field(
        default="uvicorn", description="WSGI/ASGI server for VPS deployment"
    )

    # Cloudflare Workers specific settings
    cf_workers_compatibility_date: str = Field(
        default="2024-01-01", description="Cloudflare Workers compatibility date"
    )
    cf_workers_memory_limit: int = Field(default=128, description="Memory limit in MB for Cloudflare Workers")
    cf_workers_timeout: int = Field(default=30, description="Timeout in seconds for Cloudflare Workers")
    cf_workers_kv_namespace: str | None = Field(default=None, description="Cloudflare KV namespace binding")
    cf_workers_d1_database: str | None = Field(default=None, description="Cloudflare D1 database binding")

    # Auto-scaling and performance settings
    auto_scale_workers: bool = Field(default=False, description="Enable automatic worker scaling")
    min_workers: int = Field(default=1, description="Minimum number of workers")
    max_workers: int = Field(default=16, description="Maximum number of workers")
    worker_memory_limit: int = Field(default=512, description="Memory limit per worker in MB")

    # Sentry settings
    sentry_dsn: str | None = Field(default=None, description="Sentry DSN for error tracking")
    sentry_trace_sample_rate: float = Field(default=0.1, description="Sentry trace sample rate")
    sentry_profiles_sample_rate: float = Field(default=0.1, description="Sentry profiles sample rate")
    sentry_client_dsn: str | None = Field(default=None, description="Client side Sentry DSN for error tracking")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    def model_post_init(self, __context: object) -> None:
        super().model_post_init(__context)
        required_fields = [
            "database_url",
            # "celery_broker_url",
            # "celery_result_backend",
            "supabase_url",
            "supabase_anon_key",
            "supabase_service_key",
            # "stripe_secret_key",
            # "stripe_webhook_secret",
            # "stripe_publishable_key",
            "jwt_secret_key",
        ]
        for field_name in required_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f"Missing required configuration: {field_name}")

    @field_validator("environment")
    @classmethod  # Add this decorator
    def validate_environment(cls, v: str) -> str:
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v

    @property
    def is_debug(self) -> bool:
        """Check if the application is in debug mode."""
        return self.environment == "development"


default_settings = Settings()  # Load settings from environment variables and defaults


###############################################################################
# Definee logger settings
###############################################################################
def get_default_logger_config() -> dict[str, Any]:
    return {
        "console": {
            "enabled": True,
            "correlation_id_length": 8,
            "show_logger_name": False,
            "colorize_level": True,
        },
        "file": {
            "enabled": True,
            "format": "json",
            "path": "logs/app.log",
            "encoding": "utf-8",
            "mode": "a",
        },
        "external_loggers": {
            "propagate": [
                "uvicorn",
                "uvicorn.error",
                "uvicorn.access",
            ],
            "ignore": ["aiosqlite", "sentry_sdk.errors"],
        },
    }


###############################################################################
# get always allowed paths
###############################################################################
def get_default_allowed_paths() -> list[str]:
    return [
        "/docs",  # Swagger UI
        "/docs/oauth2-redirect",  # Swagger OAuth2 redirect
        "/redoc",  # ReDoc UI
        "/openapi.json",  # OpenAPI schema
        "/health",  # Health check endpoint
        "/metrics",  # Prometheus metrics endpoint
        "/favicon.ico",  # Favicon
        "/static",  # Static files
        "/static/",  # Static files
        "/static/*",  # Static files
    ]
