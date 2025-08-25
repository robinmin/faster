"""Unit tests for the DatabaseManager."""

import asyncio
import logging
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

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
def mock_create_async_engine(mocker: MagicMock) -> MagicMock:
    """
    Mocks the create_async_engine function to return a new mock engine on each call.
    This prevents mock objects from being shared between master and replica engines.
    """

    def engine_factory(*args, **kwargs):
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

    return mocker.patch("faster.core.database.create_async_engine", side_effect=engine_factory)


class TestDatabaseManagerInitialization:
    """Tests for the initial state and setup of the DatabaseManager."""

    def test_initial_state_is_none(self, db_manager: DatabaseManager):
        """
        Arrange: A new DatabaseManager instance.
        Act: -
        Assert: All engine and session attributes are initially None.
        """
        assert db_manager.master_engine is None
        assert db_manager.replica_engine is None
        assert db_manager.master_session is None
        assert db_manager.replica_session is None

    @pytest.mark.asyncio
    async def test_setup_master_only_success(
        self, db_manager: DatabaseManager, mock_create_async_engine: MagicMock, caplog
    ):
        """
        Arrange: A DatabaseManager and a mocked engine creator.
        Act: Call setup with only a master URL.
        Assert: Correctly initializes the master engine and session, leaving replica as None.
        """
        with caplog.at_level(logging.INFO):
            await db_manager.setup(master_url=TEST_MASTER_URL)

        mock_create_async_engine.assert_called_once()
        assert db_manager.master_engine is not None
        assert db_manager.master_session is not None
        assert db_manager.replica_engine is None
        assert db_manager.replica_session is None
        assert "Master DB engine initialized" in caplog.text

    @pytest.mark.asyncio
    async def test_setup_with_replica_success(
        self, db_manager: DatabaseManager, mock_create_async_engine: MagicMock, caplog
    ):
        """
        Arrange: A DatabaseManager and a mocked engine creator.
        Act: Call setup with both master and replica URLs.
        Assert: Correctly initializes both master and replica engines and sessions.
        """
        with caplog.at_level(logging.INFO):
            await db_manager.setup(master_url=TEST_MASTER_URL, replica_url=TEST_REPLICA_URL)

        assert mock_create_async_engine.call_count == 2
        assert db_manager.master_engine is not None
        assert db_manager.master_session is not None
        assert db_manager.replica_engine is not None
        assert db_manager.replica_session is not None
        assert "Master DB engine initialized" in caplog.text
        assert "Replica DB engine initialized" in caplog.text

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
        expected_args: dict,
    ):
        """
        Arrange: A DatabaseManager and a mocked engine creator.
        Act: Call setup with different database URLs.
        Assert: The engine is created with the correct arguments based on the DB type.
        """
        await db_manager.setup(master_url=url)

        call_args = mock_create_async_engine.call_args[1]
        for key, value in expected_args.items():
            assert call_args[key] == value

    @pytest.mark.asyncio
    async def test_setup_raises_dberror_on_failure(
        self, db_manager: DatabaseManager, mock_create_async_engine: MagicMock, caplog
    ):
        """
        Arrange: A mocked engine creator that raises an exception.
        Act: Call setup.
        Assert: A DBError is raised and an error is logged.
        """
        mock_create_async_engine.side_effect = ValueError("Connection refused")
        with (
            caplog.at_level(logging.ERROR),
            pytest.raises(
                DBError,
                match="Failed to initialize database engines: Connection refused",
            ),
        ):
            await db_manager.setup(master_url=TEST_MASTER_URL)
        assert "Failed to initialize database engines" in caplog.text

    @pytest.mark.asyncio
    async def test_close_disposes_engines_and_resets_state(
        self, db_manager: DatabaseManager, mock_create_async_engine: MagicMock, caplog
    ):
        """
        Arrange: A DatabaseManager with initialized engines.
        Act: Call the close method.
        Assert: Both engines' dispose methods are called and attributes are reset to None.
        """
        await db_manager.setup(master_url=TEST_MASTER_URL, replica_url=TEST_REPLICA_URL)
        master_engine_mock = db_manager.master_engine
        replica_engine_mock = db_manager.replica_engine

        with caplog.at_level(logging.INFO):
            await db_manager.close()

        master_engine_mock.dispose.assert_awaited_once()
        replica_engine_mock.dispose.assert_awaited_once()
        assert db_manager.master_engine is None
        assert db_manager.replica_engine is None
        assert "Master DB engine disposed" in caplog.text
        assert "Replica DB engine disposed" in caplog.text


class TestDatabaseManagerSessionHandling:
    """Tests for session generation and transaction management."""

    @pytest.fixture(autouse=True)
    def setup(self, db_manager: DatabaseManager, mock_create_async_engine: MagicMock):
        """Auto-used fixture to initialize the db_manager for session tests."""
        asyncio.run(db_manager.setup(master_url=TEST_MASTER_URL, replica_url=TEST_REPLICA_URL))

    @pytest.mark.asyncio
    async def test_get_db_raises_dberror_if_not_initialized(self):
        """
        Arrange: A non-initialized DatabaseManager.
        Act: Attempt to get a DB session.
        Assert: A DBError is raised.
        """
        db_manager = DatabaseManager()  # Fresh instance
        with pytest.raises(DBError, match="Database not initialized"):
            async for _ in db_manager.get_db():
                pass  # pragma: no cover

    @pytest.mark.parametrize(
        "readonly, use_replica, expected_session_attr",
        [
            (False, True, "master_session"),  # Default case
            (True, True, "replica_session"),  # Readonly with replica available
            (True, False, "master_session"),  # Readonly but no replica configured
        ],
    )
    @pytest.mark.asyncio
    async def test_get_db_session_selection(
        self,
        db_manager: DatabaseManager,
        mocker: MagicMock,
        readonly: bool,
        use_replica: bool,
        expected_session_attr: str,
    ):
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

        async for session in db_manager.get_db(readonly=readonly):
            assert session is mock_session

        mock_session_factory.assert_called_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_transaction_success_commits_and_closes(self, db_manager: DatabaseManager, mocker: MagicMock):
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

    @pytest.mark.asyncio
    async def test_get_transaction_failure_rolls_back_and_raises(
        self, db_manager: DatabaseManager, mocker: MagicMock, caplog
    ):
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

        with (
            caplog.at_level(logging.ERROR),
            pytest.raises(DBError, match="Transaction failed, rolling back: Constraint violation"),
        ):
            async with db_manager.get_transaction():
                pass  # This code is not reached

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()
        assert "Transaction failed, rolling back" in caplog.text


class TestDatabaseManagerModelsAndHealth:
    """Tests for database model initialization and health checks."""

    @pytest.fixture(autouse=True)
    def setup(self, db_manager: DatabaseManager, mock_create_async_engine: MagicMock):
        """Auto-used fixture to initialize the db_manager for these tests."""
        asyncio.run(db_manager.setup(master_url=TEST_MASTER_URL, replica_url=TEST_REPLICA_URL))

    @pytest.mark.asyncio
    async def test_init_db_models_raises_dberror_if_not_initialized(self):
        """
        Arrange: A non-initialized DatabaseManager.
        Act: Attempt to initialize DB models.
        Assert: A DBError is raised.
        """
        db_manager = DatabaseManager()  # Fresh instance
        with pytest.raises(DBError, match="Database not initialized"):
            await db_manager.init_db_models()

    @patch("faster.core.database.SQLModel.metadata")
    @pytest.mark.asyncio
    async def test_init_db_models_creates_tables(self, mock_metadata: MagicMock, db_manager: DatabaseManager):
        """
        Arrange: A configured DatabaseManager and mocked SQLModel metadata.
        Act: Call init_db_models.
        Assert: Only create_all is called on the metadata.
        """
        await db_manager.init_db_models(drop_all=False)

        # The mock engine is configured in the fixture to handle the context manager
        # and provide a mock connection with a mock run_sync
        mock_run_sync = db_manager.master_engine.begin.return_value.__aenter__.return_value.run_sync
        mock_run_sync.assert_awaited_once_with(mock_metadata.create_all)
        assert not mock_metadata.drop_all.called

    @patch("faster.core.database.SQLModel.metadata")
    @pytest.mark.asyncio
    async def test_init_db_models_drops_and_creates_tables(
        self, mock_metadata: MagicMock, db_manager: DatabaseManager, caplog
    ):
        """
        Arrange: A configured DatabaseManager and mocked SQLModel metadata.
        Act: Call init_db_models with drop_all=True.
        Assert: Both drop_all and create_all are called, and a warning is logged.
        """
        with caplog.at_level(logging.WARNING):
            await db_manager.init_db_models(drop_all=True)

        mock_run_sync = db_manager.master_engine.begin.return_value.__aenter__.return_value.run_sync
        assert mock_run_sync.call_count == 2
        mock_run_sync.assert_any_await(mock_metadata.drop_all)
        mock_run_sync.assert_any_await(mock_metadata.create_all)
        assert "Dropping all tables..." in caplog.text

    @pytest.mark.asyncio
    async def test_check_health_all_ok(self, db_manager: DatabaseManager):
        """
        Arrange: Mocked engines that successfully return a value for 'SELECT 1'.
        Act: Call check_health.
        Assert: Returns a dict indicating both master and replica are healthy.
        """
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        db_manager.master_engine.connect.return_value.__aenter__.return_value.execute.return_value = mock_result
        db_manager.replica_engine.connect.return_value.__aenter__.return_value.execute.return_value = mock_result

        result = await db_manager.check_health()
        assert result == {"master": True, "replica": True}

    @pytest.mark.asyncio
    async def test_check_health_master_fails(self, db_manager: DatabaseManager, caplog):
        """
        Arrange: A mocked master engine that fails and a healthy replica.
        Act: Call check_health.
        Assert: Returns a dict indicating master failed and replica is healthy.
        """
        db_manager.master_engine.connect.side_effect = ConnectionRefusedError
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        db_manager.replica_engine.connect.return_value.__aenter__.return_value.execute.return_value = mock_result

        with caplog.at_level(logging.ERROR):
            result = await db_manager.check_health()

        assert result == {"master": False, "replica": True}
        assert "Health check failed for master DB" in caplog.text

    @pytest.mark.asyncio
    async def test_check_health_no_engines_configured(self):
        """
        Arrange: A DatabaseManager with no engines configured.
        Act: Call check_health.
        Assert: Returns a dict indicating both are unavailable.
        """
        db_manager = DatabaseManager()
        result = await db_manager.check_health()
        assert result == {"master": False, "replica": False}
