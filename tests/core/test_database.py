"""
Tests for the database module.
"""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_mock import MockerFixture
from sqlmodel import Field, SQLModel

from faster.core.database import (
    DatabaseManager,
    database_manager,
    db_read,
    db_write,
    health_check,
    is_sqlite_db,
)


# Sample model for database operations
class SampleModel(SQLModel, table=True):
    """Sample model for database operations."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="test")


class TestIsSqliteDb:
    """Test the is_sqlite_db function."""

    def test_is_sqlite_db_with_sqlite_url(self) -> None:
        """Test is_sqlite_db returns True for SQLite URLs."""
        assert is_sqlite_db("sqlite:///test.db") is True
        assert is_sqlite_db("sqlite+aiosqlite:///test.db") is True

    def test_is_sqlite_db_with_non_sqlite_url(self) -> None:
        """Test is_sqlite_db returns False for non-SQLite URLs."""
        assert is_sqlite_db("postgresql://user:pass@localhost/db") is False
        assert is_sqlite_db("mysql://user:pass@localhost/db") is False

    def test_is_sqlite_db_with_none(self) -> None:
        """Test is_sqlite_db returns False for None."""
        assert is_sqlite_db(None) is False

    def test_is_sqlite_db_with_empty_string(self) -> None:
        """Test is_sqlite_db returns False for empty string."""
        assert is_sqlite_db("") is False


class TestDatabaseManager:
    """Test the DatabaseManager class."""

    @pytest.fixture
    def database_manager(self) -> DatabaseManager:
        """Fixture for DatabaseManager instance."""
        return DatabaseManager()

    @pytest.mark.asyncio
    async def test_initialize_with_none_url_raises_value_error(self, database_manager: DatabaseManager) -> None:
        """Test initialize raises ValueError when database_url is None."""
        with pytest.raises(ValueError, match="Database URL cannot be None during initialization"):
            await database_manager.initialize(None)

    @pytest.mark.asyncio
    async def test_initialize_creates_engine_and_session_factory(self, database_manager: DatabaseManager) -> None:
        """Test initialize creates engine and session factory."""
        await database_manager.initialize("sqlite+aiosqlite:///:memory:")

        assert database_manager.async_engine is not None
        assert database_manager.AsyncSessionLocal is not None

    @pytest.mark.asyncio
    async def test_close_disposes_engine(self, database_manager: DatabaseManager) -> None:
        """Test close disposes the engine."""
        await database_manager.initialize("sqlite+aiosqlite:///:memory:")
        assert database_manager.async_engine is not None

        # Create a mock engine to test the dispose call
        mock_engine = AsyncMock()
        original_engine = database_manager.async_engine
        database_manager.async_engine = mock_engine

        await database_manager.close()
        mock_engine.dispose.assert_awaited_once()

        # Restore original engine
        database_manager.async_engine = original_engine


class TestDatabaseFunctions:
    """Test the database utility functions."""

    @pytest.mark.asyncio
    async def test_db_read_calls_database_manager_read(self, mocker: MockerFixture) -> None:
        """Test db_read calls database_manager.read with correct parameters."""
        mock_read = mocker.patch("faster.core.database.database_manager.read", new_callable=AsyncMock)
        mock_read.return_value = ["test_result"]

        result = await db_read(SampleModel, {"id": 1}, name="test")

        mock_read.assert_awaited_once_with(SampleModel, id=1, name="test")
        assert result == ["test_result"]

    @pytest.mark.asyncio
    async def test_db_write_calls_database_manager_write(self, mocker: MockerFixture) -> None:
        """Test db_write calls database_manager.write with correct parameters."""
        mock_write = mocker.patch("faster.core.database.database_manager.write", new_callable=AsyncMock)
        mock_write.return_value = True

        instance = SampleModel(name="test")
        result = await db_write(instance)

        mock_write.assert_awaited_once_with(instance)
        assert result is True


class TestHealthCheck:
    """Test the health_check function."""

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_engine_not_initialized(self) -> None:
        """Test health_check returns False when engine is not initialized."""
        # Store original engine and set to None
        original_engine = database_manager.async_engine
        database_manager.async_engine = None

        with patch("faster.core.database.logger") as mock_logger:
            result = await health_check()
            assert result is False
            mock_logger.warning.assert_called_once_with("Database engine not initialized for health check.")

        # Restore original engine
        database_manager.async_engine = original_engine

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_success(self) -> None:
        """Test health_check returns True when successful."""
        # Initialize with in-memory database
        await database_manager.initialize("sqlite+aiosqlite:///:memory:")

        with patch("faster.core.database.logger") as mock_logger:
            result = await health_check()
            assert result is True
            mock_logger.info.assert_called_once_with("Database health check successful.")
