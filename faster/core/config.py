from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    enable_docs: bool = Field(default=True, description="Enable API documentation")

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
    redis_url: str | None = Field(default=None, description="Redis connection URL")
    redis_max_connections: int = Field(default=50, description="Maximum number of Redis connections")
    redis_decode_responses: bool = Field(default=True, description="Automatically decode Redis responses")
    redis_required: bool = Field(default=False, description="Whether Redis is required")

    # Celery settings
    celery_broker_url: str | None = Field(default=None, description="Celery Broker URL")
    celery_result_backend: str | None = Field(default=None, description="Celery result backend")
    celery_task_always_eager: bool = Field(default=False, description="Execute Celery tasks synchronously")

    # Supabase settings
    supabase_url: str | None = Field(default=None, description="Supabase project URL")
    supabase_anon_key: str | None = Field(default=None, description="Supabase anonymous key")
    supabase_service_key: str | None = Field(default=None, description="Supabase service key")

    # Stripe settings
    stripe_secret_key: str | None = Field(default=None, description="Stripe secret key")
    stripe_webhook_secret: str | None = Field(default=None, description="Stripe webhook secret")
    stripe_publishable_key: str | None = Field(default=None, description="Stripe publishable key")

    # Security settings
    secret_key: str | None = Field(default=None, description="Application secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiry_minutes: int = Field(default=60, description="JWT expiry time in minutes")
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")
    cors_credentials: bool = Field(default=True, description="Allow CORS credentials")
    cors_enabled: bool = Field(default=True, description="Enable CORS")
    cors_allow_methods: list[str] = Field(default=["*"], description="Allowed CORS methods")
    cors_allow_headers: list[str] = Field(default=["*"], description="Allowed CORS headers")
    cors_expose_headers: list[str] = Field(default=[], description="Exposed CORS headers")
    gzip_enabled: bool = Field(default=True, description="Enable GZip compression")
    gzip_min_size: int = Field(default=1000, description="Minimum size for GZip compression")
    trusted_hosts: list[str] = Field(default=["*"], description="Trusted hosts")

    # Logging settings
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(default="json", description="Log format")
    log_file: str | None = Field(default=None, description="Path to log file")

    # Deployment adapter
    # deployment_adapter: str = Field(default="asgi", description="Deployment adapter type")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    def model_post_init(self, __context: object) -> None:
        super().model_post_init(__context)
        required_fields = [
            "database_url",
            "redis_url",
            "celery_broker_url",
            "celery_result_backend",
            "supabase_url",
            "supabase_anon_key",
            "supabase_service_key",
            "stripe_secret_key",
            "stripe_webhook_secret",
            "stripe_publishable_key",
            "secret_key",
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
