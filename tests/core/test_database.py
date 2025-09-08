"""Unit tests for the DatabaseManager."""

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from faster.core.config import Settings
from faster.core.database import DatabaseManager
from faster.core.exceptions import DBError

# Constants for database URLs
TEST_MASTER_URL = "postgresql+asyncpg://test:test@localhost/master"
TEST_REPLICA_URL = "postgresql+asyncpg://test:test@localhost/replica"
TEST_SQLITE_URL = "sqlite+aiosqlite:///test.db"


@pytest.fixture
def db_manager() -> DatabaseManager:
    """Provides a clean DatabaseManager instance for each test."""
    return DatabaseManager()


@pytest.fixture
def master_only_settings() -> Settings:
    """Settings with only master database URL."""
    return Settings(
        database_url=TEST_MASTER_URL,
        database_pool_size=5,
        database_max_overflow=10,
        database_echo=False,
    )


@pytest.fixture
def master_replica_settings() -> Settings:
    """Settings with both master database URL (replica not supported in current Settings)."""
    return Settings(
        database_url=TEST_MASTER_URL,
        database_pool_size=5,
        database_max_overflow=10,
        database_echo=False,
    )


@pytest.fixture
def mock_create_async_engine(mocker: Any) -> MagicMock:
    """
    Mocks the create_async_engine function to return a new mock engine on each call.
    This prevents mock objects from being shared between master and replica engines.
    """

    def engine_factory(*args: Any, **kwargs: Any) -> Any:
        engine = mocker.AsyncMock(spec=AsyncEngine)
        engine.dispose = mocker.AsyncMock()
        # Mock the async context manager for engine.begin()
        conn_context = mocker.AsyncMock()
        conn_context.__aenter__.return_value.run_sync = mocker.AsyncMock()
        engine.begin.return_value = conn_context
        # Mock the async context manager for engine.connect()
        connect_context = mocker.AsyncMock()
        connect_context.__aenter__.return_value.execute = mocker.AsyncMock()
        engine.connect.return_value = connect_context
        return engine

    return mocker.patch("faster.core.database.create_async_engine", side_effect=engine_factory)  # type: ignore[no-any-return]


class TestDatabaseManagerInitialization:
    """Tests for the initial state and setup of the DatabaseManager."""

    def test_initial_state_is_none(self, db_manager: DatabaseManager) -> None:
        """
        Arrange: A new DatabaseManager instance.
        Act: -
        Assert: All engine and session attributes are initially None.
        """
        assert db_manager.master_engine is None
        assert db_manager.replica_engine is None
        assert db_manager.master_session is None
        assert db_manager.replica_session is None

    @patch("faster.core.database.logger")
    @pytest.mark.asyncio
    async def test_setup_master_only_success(
        self,
        mock_logger: MagicMock,
        db_manager: DatabaseManager,
        mock_create_async_engine: MagicMock,
        master_only_settings: Settings,
    ) -> None:
        """
        Arrange: A DatabaseManager and a mocked engine creator.
        Act: Call setup with only a master URL.
        Assert: Correctly initializes the master engine and session, leaving replica as None.
        """
        _ = await db_manager.setup(master_only_settings)

        mock_create_async_engine.assert_called_once()
        assert db_manager.master_engine is not None
        assert db_manager.master_session is not None
        assert db_manager.replica_engine is None
        assert db_manager.replica_session is None
        mock_logger.info.assert_called_with("Master DB engine initialized", extra={"url": TEST_MASTER_URL})

    @patch("faster.core.database.logger")
    @pytest.mark.asyncio
    async def test_setup_master_only_via_settings(
        self,
        mock_logger: MagicMock,
        db_manager: DatabaseManager,
        mock_create_async_engine: MagicMock,
        master_replica_settings: Settings,
    ) -> None:
        """
        Arrange: A DatabaseManager and a mocked engine creator.
        Act: Call setup with master URL via Settings.
        Assert: Correctly initializes only the master engine and session (replica not supported in current Settings).
        """
        _ = await db_manager.setup(master_replica_settings)

        assert mock_create_async_engine.call_count == 1
        assert db_manager.master_engine is not None
        assert db_manager.master_session is not None
        assert db_manager.replica_engine is None
        assert db_manager.replica_session is None
        mock_logger.info.assert_any_call("Master DB engine initialized", extra={"url": TEST_MASTER_URL})

    @pytest.mark.parametrize(
        "url, expected_args",
        [
            (TEST_SQLITE_URL, {"connect_args": {"check_same_thread": False}}),
            (TEST_MASTER_URL, {"pool_size": 10, "max_overflow": 20}),
        ],
    )
    @pytest.mark.asyncio
    async def test_make_engine_arguments(
        self,
        db_manager: DatabaseManager,
        mock_create_async_engine: MagicMock,
        url: str,
        expected_args: dict[str, Any],
    ) -> None:
        """
        Arrange: A DatabaseManager and a mocked engine creator.
        Act: Call setup with different database URLs.
        Assert: The engine is created with the correct arguments based on the DB type.
        """
        settings = Settings(database_url=url, database_pool_size=10, database_max_overflow=20)
        _ = await db_manager.setup(settings)

        call_args = mock_create_async_engine.call_args[1]
        for key, value in expected_args.items():
            assert call_args[key] == value

    @patch("faster.core.database.logger")
    @pytest.mark.asyncio
    async def test_setup_raises_dberror_on_failure(
        self, mock_logger: MagicMock, db_manager: DatabaseManager, mock_create_async_engine: MagicMock
    ) -> None:
        """
        Arrange: A mocked engine creator that raises an exception.
        Act: Call setup.
        Assert: Setup returns False and an error is logged.
        """
        mock_create_async_engine.side_effect = ValueError("Connection refused")
        settings = Settings(database_url=TEST_MASTER_URL)
        success = await db_manager.setup(settings)
        assert success is False
        mock_logger.error.assert_called_with("Failed to initialize database engines: Connection refused")

    @patch("faster.core.database.logger")
    @pytest.mark.asyncio
    async def test_teardown_disposes_engines_and_resets_state(
        self, mock_logger: MagicMock, db_manager: DatabaseManager, mock_create_async_engine: MagicMock
    ) -> None:
        """
        Arrange: A DatabaseManager with initialized engines.
        Act: Call the teardown method.
        Assert: Engine dispose method is called and attributes are reset to None.
        """
        settings = Settings(database_url=TEST_MASTER_URL)
        _ = await db_manager.setup(settings)
        master_engine_mock = db_manager.master_engine

        _ = await db_manager.teardown()

        if master_engine_mock is not None:
            master_engine_mock.dispose.assert_awaited_once()  # type: ignore[attr-defined]
        assert db_manager.master_engine is None
        assert db_manager.replica_engine is None
        mock_logger.info.assert_any_call("Master DB engine disposed")


class TestDatabaseManagerSessionHandling:
    """Tests for session generation and transaction management."""

    @pytest.fixture(autouse=True)
    def setup(self, db_manager: DatabaseManager, mock_create_async_engine: MagicMock) -> None:
        """Auto-used fixture to initialize the db_manager for session tests."""
        settings = Settings(database_url=TEST_MASTER_URL)
        _ = asyncio.run(db_manager.setup(settings))

    @pytest.mark.asyncio
    async def test_get_raw_session_raises_dberror_if_not_initialized(self) -> None:
        """
        Arrange: A non-initialized DatabaseManager.
        Act: Attempt to get a DB session.
        Assert: A DBError is raised.
        """
        db_manager = DatabaseManager()  # Fresh instance
        with pytest.raises(DBError, match="Database not initialized"):
            async with db_manager.get_session() as session:
                _ = session  # pragma: no cover

    @pytest.mark.parametrize(
        "readonly, use_replica, expected_session_attr",
        [
            (False, True, "master_session"),  # Default case
            (True, True, "replica_session"),  # Readonly with replica available
            (True, False, "master_session"),  # Readonly but no replica configured
        ],
    )
    @pytest.mark.asyncio
    async def test_get_raw_session_session_selection(
        self,
        db_manager: DatabaseManager,
        mocker: Any,
        readonly: bool,
        use_replica: bool,
        expected_session_attr: str,
    ) -> None:
        """
        Arrange: A configured DatabaseManager.
        Act: Request a session with different readonly flags.
        Assert: The correct session (master or replica) is yielded and closed.
        """
        if not use_replica:
            db_manager.replica_session = None  # Simulate no replica

        mock_session = mocker.AsyncMock()
        # Replace the session factory (e.g., db_manager.master_session) with a mock that returns our mock_session
        mock_session_factory = mocker.MagicMock(return_value=mock_session)
        mocker.patch.object(db_manager, expected_session_attr, mock_session_factory)

        async with db_manager.get_session(readonly=readonly) as session:
            assert session is mock_session

        mock_session_factory.assert_called_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_txn_success_commits_and_closes(self, db_manager: DatabaseManager, mocker: Any) -> None:
        """
        Arrange: A mocked session that successfully completes a transaction.
        Act: Use the async transaction context manager.
        Assert: The session begins a transaction, is yielded, and then closed without rollback.
        """
        mock_session = mocker.AsyncMock()
        # session.begin() is a sync method returning an async context manager
        mock_session.begin = mocker.MagicMock(return_value=mocker.AsyncMock())
        # Replace the session factory with a mock that returns our mock_session
        mock_session_factory = mocker.MagicMock(return_value=mock_session)
        mocker.patch.object(db_manager, "master_session", mock_session_factory)

        async with db_manager.get_transaction() as session:
            assert session is mock_session

        mock_session.begin.assert_called_once()
        assert not mock_session.rollback.called
        mock_session.close.assert_awaited_once()

    @patch("faster.core.database.logger")
    @pytest.mark.asyncio
    async def test_get_txn_failure_rolls_back_and_raises(
        self, mock_logger: MagicMock, db_manager: DatabaseManager, mocker: Any
    ) -> None:
        """
        Arrange: A mocked session where the transaction fails.
        Act: Use the transaction context manager and raise an exception inside.
        Assert: The transaction is rolled back, a DBError is raised, and an error is logged.
        """
        mock_session = mocker.AsyncMock()
        # session.begin() is a sync method returning an async context manager
        mock_session.begin = mocker.MagicMock(return_value=mocker.AsyncMock())
        # Make the __aenter__ of the context manager raise an error
        mock_session.begin.return_value.__aenter__.side_effect = ValueError("Constraint violation")
        # Replace the session factory with a mock that returns our mock_session
        mock_session_factory = mocker.MagicMock(return_value=mock_session)
        mocker.patch.object(db_manager, "master_session", mock_session_factory)

        with pytest.raises(DBError, match="Transaction failed: Constraint violation"):
            async with db_manager.get_transaction():
                pass  # This code is not reached

        # The `async with session.begin()` context manager handles the rollback automatically.
        # We just need to ensure the session is closed and the error is logged.
        mock_session.close.assert_awaited_once()
        mock_logger.error.assert_called_once_with("Transaction failed: Constraint violation")


class TestDatabaseManagerModelsAndHealth:
    """Tests for database model initialization and health checks."""

    @pytest.fixture(autouse=True)
    def setup(self, db_manager: DatabaseManager, mock_create_async_engine: MagicMock) -> None:
        """Auto-used fixture to initialize the db_manager for these tests."""
        settings = Settings(database_url=TEST_MASTER_URL)
        _ = asyncio.run(db_manager.setup(settings))

    @pytest.mark.asyncio
    async def test_init_db_models_raises_dberror_if_not_initialized(self) -> None:
        """
        Arrange: A non-initialized DatabaseManager.
        Act: Attempt to initialize DB models.
        Assert: A DBError is raised.
        """
        db_manager = DatabaseManager()  # Fresh instance
        with pytest.raises(DBError, match="Database not initialized"):
            await db_manager.init_db_models()

    @patch("faster.core.database.SQLModel.metadata")
    @patch("faster.core.database.logger")
    @pytest.mark.asyncio
    async def test_init_db_models_creates_tables(
        self, mock_logger: MagicMock, mock_metadata: MagicMock, db_manager: DatabaseManager
    ) -> None:
        """
        Arrange: A configured DatabaseManager and mocked SQLModel metadata.
        Act: Call init_db_models.
        Assert: Only create_all is called on the metadata.
        """
        await db_manager.init_db_models(drop_all=False)

        # The mock engine is configured in the fixture to handle the context manager
        # and provide a mock connection with a mock run_sync
        mock_run_sync = db_manager.master_engine.begin.return_value.__aenter__.return_value.run_sync  # type: ignore[union-attr]
        mock_run_sync.assert_awaited_once_with(mock_metadata.create_all)
        assert not mock_metadata.drop_all.called
        mock_logger.info.assert_any_call("Creating all tables...")

    @patch("faster.core.database.SQLModel.metadata")
    @patch("faster.core.database.logger")
    @pytest.mark.asyncio
    async def test_init_db_models_drops_and_creates_tables(
        self, mock_logger: MagicMock, mock_metadata: MagicMock, db_manager: DatabaseManager
    ) -> None:
        """
        Arrange: A configured DatabaseManager and mocked SQLModel metadata.
        Act: Call init_db_models with drop_all=True.
        Assert: Both drop_all and create_all are called, and a warning is logged.
        """
        await db_manager.init_db_models(drop_all=True)

        mock_run_sync = db_manager.master_engine.begin.return_value.__aenter__.return_value.run_sync  # type: ignore[union-attr]
        assert mock_run_sync.call_count == 2
        mock_run_sync.assert_any_await(mock_metadata.drop_all)
        mock_run_sync.assert_any_await(mock_metadata.create_all)
        mock_logger.warning.assert_called_once_with("Dropping all tables...")

    @pytest.mark.asyncio
    async def test_check_health_master_ok(self, db_manager: DatabaseManager) -> None:
        """
        Arrange: Mocked master engine that successfully returns a value for 'SELECT 1'.
        Act: Call check_health.
        Assert: Returns a dict indicating master is healthy and replica is false (not configured).
        """
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        db_manager.master_engine.connect.return_value.__aenter__.return_value.execute.return_value = mock_result  # type: ignore[union-attr]

        result = await db_manager.check_health()
        assert result == {"master": True, "replica": False}

    @patch("faster.core.database.logger")
    @pytest.mark.asyncio
    async def test_check_health_master_fails(self, mock_logger: MagicMock, db_manager: DatabaseManager) -> None:
        """
        Arrange: A mocked master engine that fails.
        Act: Call check_health.
        Assert: Returns a dict indicating master failed and replica is false (not configured).
        """
        error = ConnectionRefusedError("Connection refused")
        db_manager.master_engine.connect.side_effect = error  # type: ignore[union-attr]

        result = await db_manager.check_health()

        assert result == {"master": False, "replica": False}
        mock_logger.exception.assert_called_once_with(f"Health check failed for master DB: {error}")

    @pytest.mark.asyncio
    async def test_check_health_no_engines_configured(self) -> None:
        """
        Arrange: A DatabaseManager with no engines configured.
        Act: Call check_health.
        Assert: Returns a dict indicating both are unavailable.
        """
        db_manager = DatabaseManager()
        result = await db_manager.check_health()
        assert result == {"master": False, "replica": False, "reason": "Plugin not ready"}
