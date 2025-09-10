import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from unittest.mock import patch

import pytest
from pytest import Config, FixtureRequest
import pytest_asyncio
from sqlmodel import Field

from faster.core.auth.schemas import (  # noqa: F401  # type: ignore[unused-ignore]
    User,  # type: ignore[unused-ignore]
    UserIdentity,  # type: ignore[unused-ignore]
    UserMetadata,  # type: ignore[unused-ignore]
    UserProfile,  # type: ignore[unused-ignore]
    UserRole,  # type: ignore[unused-ignore]
)
from faster.core.config import Settings
from faster.core.database import DatabaseManager, DBSession
from faster.core.redis import RedisManager

# Import ALL models to ensure they are registered with SQLModel metadata
from faster.core.schemas import SysDict, SysMap  # noqa: F401  # type: ignore[unused-ignore]


class TestMyBaseMixin:
    """
    Test-specific mixin class that uses datetime.now() for SQLite compatibility.
    This ensures timestamps are set at object creation time during tests.
    """

    in_used: int = Field(
        default=1,
        sa_column_kwargs={
            "name": "N_IN_USED",
            "server_default": "1",
        },
        description="1=active, 0=soft deleted",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={
            "name": "D_CREATED_AT",
        },
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={
            "name": "D_UPDATED_AT",
        },
        description="Last update timestamp",
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column_kwargs={
            "name": "D_DELETED_AT",
        },
        description="Soft deleting timestamp",
    )

    # Instance methods
    def soft_delete(self) -> None:
        """Soft delete the record by setting in_used=0 and recording timestamp."""
        self.in_used = 0
        self.deleted_at = datetime.now()

    def restore(self) -> None:
        """Restore soft deleted record by setting in_used=1."""
        self.in_used = 1
        self.deleted_at = None

    @property
    def is_active(self) -> bool:
        """Check if record is active (in_used=1)."""
        return self.in_used == 1

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted (in_used=0)."""
        return self.in_used == 0

    # Class methods for common query filters
    @classmethod
    def active_filter(cls) -> bool:
        """Filter for active records (in_used=1)."""
        return cls.in_used == 1

    @classmethod
    def deleted_filter(cls) -> bool:
        """Filter for soft deleted records (in_used=0)."""
        return cls.in_used == 0


# TestMyBase is now just the mixin - use it with SQLModel in tests


# TestMyBase can be used directly with table=True in test classes


# TestUserProfile will be created dynamically in tests to avoid table conflicts


def pytest_configure(config: Config) -> None:
    """
    Initializes the Redis manager with a fake provider before tests are collected.
    """
    settings = Settings(redis_provider="fake")
    _ = asyncio.run(RedisManager.get_instance().setup(settings))


@pytest.fixture(autouse=True)
def disable_sentry_for_non_sentry_tests(request: FixtureRequest) -> Generator[None, None, None]:
    """
    Auto-used fixture to disable Sentry during non-Sentry tests to prevent logging errors
    when Sentry tries to send events after test completion.
    """
    # Only disable Sentry for non-Sentry tests
    if "sentry" not in request.module.__name__:
        with (
            patch("faster.core.sentry.SentryManager.setup", return_value=True),
            patch("faster.core.sentry.init") as mock_init,
            patch("faster.core.sentry.capture_exception") as mock_capture_exception,
            patch("faster.core.sentry.capture_message") as mock_capture_message,
            patch("faster.core.sentry.is_initialized", return_value=False),
        ):
            mock_init.return_value = None
            mock_capture_exception.return_value = None
            mock_capture_message.return_value = None
            yield
    else:
        # For Sentry tests, don't mock anything
        yield


@pytest_asyncio.fixture
async def test_settings() -> Settings:
    """Create test settings with in-memory SQLite database."""
    return Settings(database_url="sqlite+aiosqlite:///:memory:", redis_provider="fake")


@pytest_asyncio.fixture
async def db_manager(test_settings: Settings) -> DatabaseManager:
    """Initialize database manager with test settings for each test."""
    # Create a new instance for each test to avoid singleton issues
    manager = DatabaseManager()
    _ = await manager.setup(test_settings)

    # Initialize database models explicitly
    await manager.init_db_models()

    return manager


@pytest_asyncio.fixture
async def db_session(db_manager: DatabaseManager) -> AsyncGenerator[DBSession, None]:
    """Create a test database session."""
    session = db_manager.create_session()
    try:
        yield session
    finally:
        await session.close()
