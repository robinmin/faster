"""Unit tests for the DatabaseManager."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import Field, SQLModel

from faster.core.config import Settings
from faster.core.database import D1Session, DatabaseManager, parse_d1_url
from faster.core.exceptions import DBError

# Constants for database URLs
TEST_MASTER_URL = "postgresql+asyncpg://test:test@localhost/master"
TEST_REPLICA_URL = "postgresql+asyncpg://test:test@localhost/replica"
TEST_SQLITE_URL = "sqlite+aiosqlite:///test.db"
TEST_D1_HTTP_URL = "d1+aiosqlite://test-db-id?account_id=test-account&api_token=test-token"
TEST_D1_BINDING_URL = "d1+binding://MY_D1_DB"


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
        mock_logger.error.assert_called_with("Failed to initialize database: Connection refused")

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
    async def test_get_session_raises_dberror_if_not_initialized(self) -> None:
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
    async def test_get_session_session_selection(
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
    async def test_get_transaction_success_commits_and_closes(self, db_manager: DatabaseManager, mocker: Any) -> None:
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
    async def test_get_transaction_failure_rolls_back_and_raises(
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
        assert result == {
            "is_ready": True,
            "master_schema": "unknown",
            "master_response": True,
            "replica_schema": None,
            "replica_response": False,
        }

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

        assert result == {
            "is_ready": True,
            "master_schema": "unknown",
            "master_response": False,
            "replica_schema": None,
            "replica_response": False,
        }
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
        assert result == {
            "is_ready": False,
            "master_schema": None,
            "master_response": False,
            "replica_schema": None,
            "replica_response": False,
            "reason": "Plugin not ready",
        }


###############################################################################
# Cloudflare D1 Tests
###############################################################################


class TestD1UrlParsing:
    """Tests for D1 URL parsing functionality."""

    def test_parse_d1_binding_url(self) -> None:
        """
        Arrange: A D1 binding URL.
        Act: Parse the URL.
        Assert: Correctly extracts binding name and sets binding mode.
        """
        connection_info = parse_d1_url(TEST_D1_BINDING_URL)
        assert connection_info["database_id"] == "MY_D1_DB"
        assert connection_info["binding_name"] == "MY_D1_DB"
        assert connection_info["is_binding"] is True
        assert connection_info["account_id"] is None
        assert connection_info["api_token"] is None

    def test_parse_d1_http_url_with_params(self) -> None:
        """
        Arrange: A D1 HTTP URL with query parameters.
        Act: Parse the URL.
        Assert: Correctly extracts database ID and credentials.
        """
        connection_info = parse_d1_url(TEST_D1_HTTP_URL)
        assert connection_info["database_id"] == "test-db-id"
        assert connection_info["account_id"] == "test-account"
        assert connection_info["api_token"] == "test-token"
        assert connection_info["is_binding"] is False
        assert connection_info["binding_name"] is None

    @patch.dict("os.environ", {"CLOUDFLARE_ACCOUNT_ID": "env-account", "CLOUDFLARE_API_TOKEN": "env-token"})
    def test_parse_d1_http_url_with_env_vars(self) -> None:
        """
        Arrange: A D1 HTTP URL without credentials and environment variables set.
        Act: Parse the URL.
        Assert: Correctly extracts credentials from environment.
        """
        url = "d1+aiosqlite://test-db-id"
        connection_info = parse_d1_url(url)
        assert connection_info["database_id"] == "test-db-id"
        assert connection_info["account_id"] == "env-account"
        assert connection_info["api_token"] == "env-token"
        assert connection_info["is_binding"] is False

    def test_parse_invalid_d1_url(self) -> None:
        """
        Arrange: An invalid D1 URL scheme.
        Act: Parse the URL.
        Assert: Raises DBError.
        """
        with pytest.raises(DBError, match="Invalid D1 URL scheme"):
            _ = parse_d1_url("invalid+scheme://database")


class TestD1DatabaseManagerSetup:
    """Tests for DatabaseManager D1 setup functionality."""

    @patch("faster.core.database.D1Client")
    @pytest.mark.asyncio
    async def test_setup_d1_http_mode_success(self, mock_d1_client_class: MagicMock, db_manager: DatabaseManager) -> None:
        """
        Arrange: A DatabaseManager and mocked D1Client.
        Act: Setup with D1 HTTP URL.
        Assert: D1 mode is enabled and client is initialized.
        """
        mock_d1_client = MagicMock()
        mock_d1_client_class.return_value = mock_d1_client

        settings = Settings(database_url=TEST_D1_HTTP_URL)
        result = await db_manager.setup(settings)

        assert result is True
        assert db_manager.is_d1_mode is True
        assert db_manager.d1_master_client is mock_d1_client
        assert db_manager.master_engine is None
        assert db_manager.master_session is None
        mock_d1_client_class.assert_called_once()

    @patch("faster.core.database.D1Client")
    @pytest.mark.asyncio
    async def test_setup_d1_binding_mode_success(self, mock_d1_client_class: MagicMock, db_manager: DatabaseManager) -> None:
        """
        Arrange: A DatabaseManager and mocked D1Client.
        Act: Setup with D1 binding URL.
        Assert: D1 mode is enabled and client is initialized.
        """
        mock_d1_client = MagicMock()
        mock_d1_client_class.return_value = mock_d1_client

        settings = Settings(database_url=TEST_D1_BINDING_URL)
        result = await db_manager.setup(settings)

        assert result is True
        assert db_manager.is_d1_mode is True
        assert db_manager.d1_master_client is mock_d1_client
        mock_d1_client_class.assert_called_once()

    @patch("faster.core.database.D1Client")
    @pytest.mark.asyncio
    async def test_setup_d1_client_creation_failure(self, mock_d1_client_class: MagicMock, db_manager: DatabaseManager) -> None:
        """
        Arrange: A DatabaseManager with D1Client that raises an exception.
        Act: Setup with D1 URL.
        Assert: Setup returns False and error is logged.
        """
        mock_d1_client_class.side_effect = DBError("Invalid credentials")

        settings = Settings(database_url=TEST_D1_HTTP_URL)
        result = await db_manager.setup(settings)

        assert result is False
        assert db_manager.is_ready is False

    def test_is_d1_url_detection(self, db_manager: DatabaseManager) -> None:
        """
        Arrange: Various URL formats.
        Act: Check if they are D1 URLs.
        Assert: Correctly identifies D1 URLs.
        """
        assert db_manager._is_d1_url(TEST_D1_HTTP_URL) is True  # pyright: ignore[reportPrivateUsage]
        assert db_manager._is_d1_url(TEST_D1_BINDING_URL) is True  # pyright: ignore[reportPrivateUsage]
        assert db_manager._is_d1_url(TEST_SQLITE_URL) is False  # pyright: ignore[reportPrivateUsage]
        assert db_manager._is_d1_url(TEST_MASTER_URL) is False  # pyright: ignore[reportPrivateUsage]


class TestD1SessionAndTransactionManagement:
    """Tests for D1 session and transaction functionality."""

    @pytest.fixture
    def mock_d1_client(self, mocker: Any) -> Any:
        """Create a mock D1Client."""
        mock = mocker.MagicMock()
        mock.execute_query = mocker.AsyncMock()
        return mock

    @pytest.fixture
    def d1_session(self, mock_d1_client: Any) -> Any:
        """Create a D1Session with mock client."""
        return D1Session(mock_d1_client)

    @pytest.mark.asyncio
    async def test_d1_session_exec_query(self, d1_session: Any, mock_d1_client: Any) -> None:
        """
        Arrange: A D1Session with mock client.
        Act: Execute a query.
        Assert: Client execute_query is called with compiled SQL.
        """
        mock_statement = MagicMock()
        mock_compiled = MagicMock()
        type(mock_compiled).__str__ = lambda self: "SELECT * FROM users"  # type: ignore[method-assign]
        mock_statement.compile.return_value = mock_compiled
        mock_d1_client.execute_query.return_value = {"results": []}

        await d1_session.exec(mock_statement)

        mock_d1_client.execute_query.assert_called_once_with("SELECT * FROM users")

    @pytest.mark.asyncio
    async def test_d1_session_get_entity(self, d1_session: Any, mock_d1_client: Any) -> None:
        """
        Arrange: A D1Session with mock client returning user data.
        Act: Get entity by ID.
        Assert: Returns constructed model instance.
        """
        class TestUser1(SQLModel, table=True):
            __tablename__ = "test_users_1"
            id: int | None = Field(default=None, primary_key=True)
            name: str

        mock_d1_client.execute_query.return_value = {
            "results": [{"id": 1, "name": "John Doe"}]
        }

        result = await d1_session.get(TestUser1, 1)

        assert result is not None
        assert result.id == 1
        assert result.name == "John Doe"
        mock_d1_client.execute_query.assert_called_once_with("SELECT * FROM test_users_1 WHERE id = ?", [1])

    @pytest.mark.asyncio
    async def test_d1_session_get_entity_not_found(self, d1_session: Any, mock_d1_client: Any) -> None:
        """
        Arrange: A D1Session with mock client returning no results.
        Act: Get entity by ID.
        Assert: Returns None.
        """
        class TestUser2(SQLModel, table=True):
            __tablename__ = "test_users_2"
            id: int | None = Field(default=None, primary_key=True)
            name: str

        mock_d1_client.execute_query.return_value = {"results": []}

        result = await d1_session.get(TestUser2, 999)

        assert result is None

    @pytest.mark.asyncio
    async def test_d1_session_add_and_flush(self, d1_session: Any, mock_d1_client: MagicMock) -> None:
        """
        Arrange: A D1Session with mock client.
        Act: Add entity and flush.
        Assert: Insert query is executed.
        """
        class TestUser3(SQLModel, table=True):
            __tablename__ = "test_users_3"
            id: int | None = Field(default=None, primary_key=True)
            name: str

        user = TestUser3(name="Jane Doe")
        d1_session.add(user)
        await d1_session.flush()

        mock_d1_client.execute_query.assert_called_once_with(
            "INSERT INTO test_users_3 (name) VALUES (?)",
            ["Jane Doe"]
        )

    @pytest.mark.asyncio
    async def test_d1_session_delete_entity(self, d1_session: Any, mock_d1_client: MagicMock) -> None:
        """
        Arrange: A D1Session with mock client.
        Act: Delete entity.
        Assert: Delete query is executed.
        """
        class TestUser4(SQLModel, table=True):
            __tablename__ = "test_users_4"
            id: int | None = Field(default=None, primary_key=True)
            name: str

        user = TestUser4(id=1, name="John Doe")
        await d1_session.delete(user)

        mock_d1_client.execute_query.assert_called_once_with("DELETE FROM test_users_4 WHERE id = ?", [1])

    @pytest.mark.asyncio
    async def test_d1_session_transaction_success(self, d1_session: Any, mock_d1_client: MagicMock) -> None:
        """
        Arrange: A D1Session with mock client.
        Act: Use transaction context manager successfully.
        Assert: Transaction auto-commits on success.
        """
        class TestUser5(SQLModel, table=True):
            __tablename__ = "test_users_5"
            id: int | None = Field(default=None, primary_key=True)
            name: str

        async with d1_session.begin() as session:
            user = TestUser5(name="Transaction User")
            session.add(user)

        # Should have auto-flushed on successful exit
        mock_d1_client.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_d1_session_closed_operations_raise_error(self, d1_session: Any) -> None:
        """
        Arrange: A closed D1Session.
        Act: Attempt operations on closed session.
        Assert: DBError is raised.
        """
        await d1_session.close()

        with pytest.raises(DBError, match="Session is closed"):
            await d1_session.exec(MagicMock())

        with pytest.raises(DBError, match="Session is closed"):
            await d1_session.get(MagicMock(), 1)

        with pytest.raises(DBError, match="Session is closed"):
            d1_session.add(MagicMock())


class TestD1DatabaseManagerOperations:
    """Tests for DatabaseManager D1-specific operations."""

    @pytest.fixture
    def d1_db_manager(self, mocker: Any) -> DatabaseManager:
        """Create a DatabaseManager in D1 mode."""
        db_manager = DatabaseManager()
        mock_d1_client = MagicMock()
        mock_d1_client.execute_query = AsyncMock()
        mock_d1_client.close = AsyncMock()

        # Set up D1 mode manually
        db_manager.is_d1_mode = True
        db_manager.d1_master_client = mock_d1_client
        db_manager.is_ready = True

        return db_manager

    @pytest.mark.asyncio
    async def test_d1_get_session_factory(self, d1_db_manager: DatabaseManager) -> None:
        """
        Arrange: A DatabaseManager in D1 mode.
        Act: Get session factory.
        Assert: Returns factory that creates D1Session.
        """
        session_factory = d1_db_manager.get_session_factory()
        session = session_factory()

        assert isinstance(session, D1Session)

    @pytest.mark.asyncio
    async def test_d1_execute_raw_query(self, d1_db_manager: DatabaseManager) -> None:
        """
        Arrange: A DatabaseManager in D1 mode.
        Act: Execute raw query.
        Assert: D1Client execute_query is called with correct parameters.
        """
        query = "SELECT * FROM users WHERE name = ? AND age = ?"
        params = {"name": "John", "age": 30}

        await d1_db_manager.execute_raw_query(query, params)

        assert d1_db_manager.d1_master_client is not None
        d1_db_manager.d1_master_client.execute_query.assert_called_once_with(  # type: ignore[attr-defined]
            query, ["John", 30]
        )

    @pytest.mark.asyncio
    async def test_d1_health_check_success(self, d1_db_manager: DatabaseManager) -> None:
        """
        Arrange: A DatabaseManager in D1 mode with working client.
        Act: Check health.
        Assert: Returns healthy status for D1.
        """
        assert d1_db_manager.d1_master_client is not None
        d1_db_manager.d1_master_client.execute_query.return_value = {"results": [{"result": 1}]}  # type: ignore[attr-defined]

        result = await d1_db_manager.check_health()

        assert result["is_ready"] is True
        assert result["master_schema"] == "d1"
        assert result["master_response"] is True
        assert result["replica_schema"] is None
        assert result["replica_response"] is False

    @patch("faster.core.database.logger")
    @pytest.mark.asyncio
    async def test_d1_health_check_failure(self, mock_logger: MagicMock, d1_db_manager: DatabaseManager) -> None:
        """
        Arrange: A DatabaseManager in D1 mode with failing client.
        Act: Check health.
        Assert: Returns failed status and logs error.
        """
        error = Exception("D1 connection failed")
        assert d1_db_manager.d1_master_client is not None
        d1_db_manager.d1_master_client.execute_query.side_effect = error  # type: ignore[attr-defined]

        result = await d1_db_manager.check_health()

        assert result["master_response"] is False
        mock_logger.exception.assert_called_once_with(f"Health check failed for master D1: {error}")

    @patch("faster.core.database.generate_ddl")
    @pytest.mark.asyncio
    async def test_d1_init_db_models_create_tables(self, mock_generate_ddl: MagicMock, d1_db_manager: DatabaseManager) -> None:
        """
        Arrange: A DatabaseManager in D1 mode.
        Act: Initialize database models.
        Assert: DDL statements are executed via D1Client.
        """
        mock_generate_ddl.return_value = "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT); CREATE INDEX idx_name ON users(name);"

        await d1_db_manager.init_db_models()

        # Should call execute_query for each DDL statement
        assert d1_db_manager.d1_master_client is not None
        assert d1_db_manager.d1_master_client.execute_query.call_count == 2  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_d1_teardown_closes_clients(self, d1_db_manager: DatabaseManager) -> None:
        """
        Arrange: A DatabaseManager in D1 mode.
        Act: Teardown.
        Assert: D1 clients are closed and state is reset.
        """
        # Store reference to client before teardown
        d1_client = d1_db_manager.d1_master_client

        result = await d1_db_manager.teardown()

        assert result is True
        assert d1_db_manager.is_d1_mode is False
        assert d1_db_manager.d1_master_client is None
        assert d1_client is not None
        d1_client.close.assert_called_once()  # type: ignore[attr-defined]
