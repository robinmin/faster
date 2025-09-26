from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager  # pyright: ignore[reportPrivateUsage]
from datetime import datetime
import os
from typing import Any, TypedDict, TypeVar, cast
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import Select

from .config import Settings
from .exceptions import DBError
from .logger import get_logger
from .plugins import BasePlugin

###############################################################################

logger = get_logger(__name__)

# Type definitions - Simplified using SQLModel's native types
ModelType = TypeVar("ModelType", bound=SQLModel)
DBSession = AsyncSession


###############################################################################
# Cloudflare D1 Adapter Classes
###############################################################################


class D1ConnectionInfo(TypedDict):
    """Type definition for D1 connection information."""
    database_id: str
    account_id: str | None
    api_token: str | None
    binding_name: str | None
    is_binding: bool


class D1Session:
    """
    Mock session that provides SQLAlchemy-compatible interface for D1 operations.
    Handles both HTTP client and Workers binding modes.
    """

    def __init__(self, d1_client: "D1Client") -> None:
        self.d1_client = d1_client
        self._closed = False
        self._in_transaction = False
        self._pending_operations: list[dict[str, Any]] = []

    async def exec(self, statement: Any) -> Any:
        """Execute a SQLModel statement and return results."""
        if self._closed:
            raise DBError("Session is closed")

        # Convert SQLModel statement to SQL
        sql_query = str(statement.compile(compile_kwargs={"literal_binds": True}))
        return await self.d1_client.execute_query(sql_query)

    async def get(self, model_class: type[ModelType], entity_id: Any) -> ModelType | None:
        """Get entity by primary key."""
        if self._closed:
            raise DBError("Session is closed")

        # Build SELECT query for primary key
        table_name = getattr(model_class, "__tablename__", model_class.__name__.lower())
        sql_query = f"SELECT * FROM {table_name} WHERE id = ?"

        result = await self.d1_client.execute_query(sql_query, [entity_id])
        if not result.get("results") or not result["results"]:
            return None

        # Convert result to model instance
        row_data = result["results"][0]
        return model_class(**row_data)

    def add(self, entity: Any) -> None:
        """Add entity to session (stage for insert)."""
        if self._closed:
            raise DBError("Session is closed")

        operation = {
            "type": "insert",
            "entity": entity,
            "table": getattr(entity.__class__, "__tablename__", entity.__class__.__name__.lower())
        }
        self._pending_operations.append(operation)

    def add_all(self, entities: list[Any]) -> None:
        """Add multiple entities to session."""
        for entity in entities:
            self.add(entity)

    async def delete(self, entity: Any) -> None:
        """Delete entity from database."""
        if self._closed:
            raise DBError("Session is closed")

        table_name = getattr(entity.__class__, "__tablename__", entity.__class__.__name__.lower())
        entity_id = getattr(entity, "id", None)
        if entity_id is None:
            raise DBError("Entity must have an 'id' attribute for deletion")

        sql_query = f"DELETE FROM {table_name} WHERE id = ?"
        _ = await self.d1_client.execute_query(sql_query, [entity_id])

    async def merge(self, entity: Any) -> Any:
        """Merge entity into session (for update operations)."""
        if self._closed:
            raise DBError("Session is closed")
        return entity

    async def flush(self) -> None:
        """Execute pending operations."""
        if self._closed:
            raise DBError("Session is closed")

        for operation in self._pending_operations:
            if operation["type"] == "insert":
                await self._execute_insert(operation["entity"], operation["table"])

        self._pending_operations.clear()

    async def _execute_insert(self, entity: Any, table_name: str) -> None:
        """Execute insert operation for an entity."""
        # Convert entity to dict, excluding None values and id if it's None
        entity_dict = entity.model_dump(exclude_none=True)
        if "id" in entity_dict and entity_dict["id"] is None:
            entity_dict.pop("id")

        if not entity_dict:
            return

        columns = list(entity_dict.keys())
        placeholders = ["?" for _ in columns]
        values = list(entity_dict.values())

        sql_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        _ = await self.d1_client.execute_query(sql_query, values)

    async def execute(self, statement: Any, parameters: dict[str, Any] | None = None) -> Any:
        """Execute raw SQL statement."""
        if self._closed:
            raise DBError("Session is closed")

        if hasattr(statement, "text"):
            sql_query = str(statement.text)
        else:
            sql_query = str(statement)

        params = list(parameters.values()) if parameters else []
        return await self.d1_client.execute_query(sql_query, params)

    def begin(self) -> "D1Transaction":
        """Begin a transaction."""
        if self._closed:
            raise DBError("Session is closed")
        return D1Transaction(self)

    async def close(self) -> None:
        """Close the session."""
        self._closed = True
        self._pending_operations.clear()


class D1Transaction:
    """Mock transaction context manager for D1."""

    def __init__(self, session: D1Session) -> None:
        self.session = session
        self._committed = False

    async def __aenter__(self) -> D1Session:
        """Enter transaction context."""
        self.session._in_transaction = True  # pyright: ignore[reportPrivateUsage]
        return self.session

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit transaction context."""
        self.session._in_transaction = False  # pyright: ignore[reportPrivateUsage]
        if exc_type is None and not self._committed:
            # Auto-commit on successful completion
            await self.session.flush()
            self._committed = True


class D1Client:
    """
    Unified client for D1 operations supporting both HTTP API and Workers binding.
    """

    def __init__(self, connection_info: D1ConnectionInfo) -> None:
        self.connection_info = connection_info
        self.http_client: httpx.AsyncClient | None = None
        self.worker_binding: Any = None

        if connection_info["is_binding"]:
            self._init_worker_binding()
        else:
            self._init_http_client()

    def _init_worker_binding(self) -> None:
        """Initialize Workers binding mode."""
        binding_name = self.connection_info["binding_name"]
        if not binding_name:
            raise DBError("Binding name is required for Workers binding mode")

        # In Workers environment, bindings are available in the global env
        # This is a placeholder - actual implementation depends on Workers runtime
        try:
            # Workers runtime would provide this via env
            # Note: js module is only available in Workers runtime
            import js  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports] # noqa: PLC0415
            self.worker_binding = getattr(js.env, binding_name, None)
            if self.worker_binding is None:
                logger.warning(f"D1 binding '{binding_name}' not found, falling back to HTTP client")
                self._init_http_client()
        except ImportError:
            logger.info("Not in Workers environment, using HTTP client")
            self._init_http_client()

    def _init_http_client(self) -> None:
        """Initialize HTTP client mode."""
        account_id = self.connection_info["account_id"]
        api_token = self.connection_info["api_token"]

        if not account_id or not api_token:
            raise DBError("Account ID and API token are required for HTTP client mode")

        self.http_client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def execute_query(self, sql: str, params: list[Any] | None = None) -> dict[str, Any]:
        """Execute SQL query using appropriate method."""
        if self.worker_binding:
            return await self._execute_via_binding(sql, params)
        if self.http_client:
            return await self._execute_via_http(sql, params)
        raise DBError("No D1 client method available")

    async def _execute_via_binding(self, sql: str, params: list[Any] | None = None) -> dict[str, Any]:
        """Execute query via Workers binding."""
        try:
            # Workers binding API
            statement = self.worker_binding.prepare(sql)
            if params:
                for param in params:
                    statement = statement.bind(param)

            result = await statement.all()
            return {
                "success": True,
                "results": result.results if hasattr(result, "results") else [],
                "meta": getattr(result, "meta", {}),
            }
        except Exception as e:
            logger.error(f"D1 binding query failed: {e}")
            raise DBError(f"D1 binding query failed: {e}") from e

    async def _execute_via_http(self, sql: str, params: list[Any] | None = None) -> dict[str, Any]:
        """Execute query via HTTP API."""
        if not self.http_client:
            raise DBError("HTTP client not initialized")

        account_id = self.connection_info["account_id"]
        database_id = self.connection_info["database_id"]

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query"

        payload: dict[str, Any] = {"sql": sql}
        if params:
            payload["params"] = params

        try:
            response = await self.http_client.post(url, json=payload)
            _ = response.raise_for_status()

            data = response.json()
            if not data.get("success", False):
                errors = data.get("errors", [])
                error_msg = "; ".join(err.get("message", str(err)) for err in errors)
                raise DBError(f"D1 query failed: {error_msg}")

            result = data.get("result", {})
            return cast(dict[str, Any], result)
        except httpx.HTTPError as e:
            logger.error(f"D1 HTTP query failed: {e}")
            raise DBError(f"D1 HTTP query failed: {e}") from e

    async def close(self) -> None:
        """Close the client."""
        if self.http_client:
            await self.http_client.aclose()


def parse_d1_url(url: str) -> D1ConnectionInfo:
    """
    Parse D1 connection string and extract connection information.

    Supported formats:
    - d1+binding://BINDING_NAME
    - d1+aiosqlite://DATABASE_ID?account_id=XXX&api_token=YYY
    """
    parsed = urlparse(url)

    if parsed.scheme == "d1+binding":
        return D1ConnectionInfo(
            database_id=parsed.netloc,
            account_id=None,
            api_token=None,
            binding_name=parsed.netloc,
            is_binding=True,
        )
    if parsed.scheme == "d1+aiosqlite":
        query_params = parse_qs(parsed.query)

        # Get credentials from URL params or environment variables
        account_id = (
            query_params.get("account_id", [None])[0] or
            os.getenv("CLOUDFLARE_ACCOUNT_ID")
        )
        api_token = (
            query_params.get("api_token", [None])[0] or
            os.getenv("CLOUDFLARE_API_TOKEN")
        )

        return D1ConnectionInfo(
            database_id=parsed.netloc,
            account_id=account_id,
            api_token=api_token,
            binding_name=None,
            is_binding=False,
        )
    raise DBError(f"Invalid D1 URL scheme: {parsed.scheme}")


###############################################################################
# Database Manager with D1 Support
###############################################################################


class EngineKwargs(TypedDict, total=False):
    echo: bool
    future: bool
    connect_args: dict[str, bool]
    pool_size: int
    max_overflow: int


class DatabaseManager(BasePlugin):
    """
    Enhanced database manager that provides abstraction layer for database access.
    Acts as a wrapper to hide implementation details from client code.
    Supports SQLite, PostgreSQL, and Cloudflare D1 databases.
    """

    def __init__(self) -> None:
        self.master_engine: AsyncEngine | None = None
        self.replica_engine: AsyncEngine | None = None
        self.master_session: async_sessionmaker[DBSession] | None = None
        self.replica_session: async_sessionmaker[DBSession] | None = None
        self.d1_master_client: D1Client | None = None
        self.d1_replica_client: D1Client | None = None
        self.is_d1_mode: bool = False
        self.is_ready: bool = False

    def _is_d1_url(self, url: str) -> bool:
        """Check if URL is a D1 connection string."""
        return url.startswith(("d1+binding://", "d1+aiosqlite://"))

    def _make_engine(self, url: str, pool_size: int, max_overflow: int, echo: bool) -> AsyncEngine:
        """Create database engine for traditional databases (SQLite, PostgreSQL)."""
        if self._is_d1_url(url):
            raise DBError("Use _create_d1_client for D1 connections")

        engine_kwargs: EngineKwargs = {"echo": echo, "future": True}

        if url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs["pool_size"] = pool_size
            engine_kwargs["max_overflow"] = max_overflow

        return create_async_engine(url, **engine_kwargs)

    def _create_d1_client(self, url: str) -> D1Client:
        """Create D1 client from connection string."""
        connection_info = parse_d1_url(url)
        return D1Client(connection_info)

    def get_session_factory(self, readonly: bool = False) -> Callable[[], DBSession]:
        """Get an async session factory function for dependency injection."""
        if self.is_d1_mode:
            # For D1, return factory that creates D1Session
            d1_client = self.d1_replica_client if readonly and self.d1_replica_client else self.d1_master_client
            if d1_client is None:
                raise DBError("D1 database not initialized. Call setup first.")
            return lambda: D1Session(d1_client)  # type: ignore[return-value]

        # Traditional database session factory
        session_factory = self.replica_session if readonly and self.replica_session else self.master_session
        if session_factory is None:
            raise DBError("Database not initialized. Call setup first.")
        return session_factory

    # Enhanced abstraction methods
    def create_session(self, readonly: bool = False) -> DBSession:
        """Create a new database session. Client code should use this instead of direct access."""
        session_factory = self.get_session_factory(readonly=readonly)
        return session_factory()

    async def execute_raw_query(self, query: str, params: dict[str, Any] | None = None, readonly: bool = True) -> Any:
        """
        Execute raw SQL query with abstraction.
        Returns results in a database-agnostic way.
        """
        if self.is_d1_mode:
            # For D1, convert dict params to list params
            d1_client = self.d1_replica_client if readonly and self.d1_replica_client else self.d1_master_client
            if d1_client is None:
                raise DBError("D1 database not initialized. Call setup first.")

            param_list = list(params.values()) if params else []
            return await d1_client.execute_query(query, param_list)

        # Traditional database execution
        async with self.get_session(readonly=readonly) as session:
            # Use execute() for raw SQL text as exec() doesn't support TextClause
            result = await session.execute(text(query), params or {})  # pyright: ignore[reportDeprecated]
            return result

    # -----------------------------
    # Session management - Simplified and consistent
    # -----------------------------
    @asynccontextmanager
    async def get_session(self, readonly: bool = False) -> AsyncGenerator[DBSession, None]:
        """
        Get a managed database session with automatic cleanup.

        Example:
            async with db_manager.get_session() as session:
                result = await session.exec(select(User))
                users = result.all()
        """
        session = self.create_session(readonly)
        try:
            yield session
        finally:
            await session.close()

    @asynccontextmanager
    async def get_transaction(self, readonly: bool = False) -> AsyncGenerator[DBSession, None]:
        """
        Get a transactional database session with automatic commit/rollback.

        Example:
            async with db_manager.get_transaction() as session:
                user = User(name="John")
                session.add(user)
                # Auto-commits on success, auto-rollbacks on exception
        """
        session = self.create_session(readonly)
        try:
            async with session.begin():
                yield session
        except Exception as exp:
            msg = f"Transaction failed: {exp}"
            logger.error(msg)
            raise DBError(msg) from exp
        finally:
            await session.close()

    # -----------------------------
    # Init models
    # -----------------------------
    async def _init_d1_models(self, drop_all: bool) -> None:
        """Initialize D1 database models."""
        if self.d1_master_client is None:
            raise DBError("D1 database not initialized. Call setup first.")

        # Generate DDL statements for D1 (SQLite dialect)
        ddl_sql = generate_ddl("sqlite:///:memory:")
        ddl_statements = [stmt.strip() for stmt in ddl_sql.split(";") if stmt.strip()]

        if drop_all:
            await self._drop_d1_tables()

        logger.info("Creating tables in D1...")
        for ddl_stmt in ddl_statements:
            if ddl_stmt:
                _ = await self.d1_master_client.execute_query(ddl_stmt)

        logger.info("D1 tables created successfully.")

    async def _drop_d1_tables(self) -> None:
        """Drop existing D1 tables."""
        if self.d1_master_client is None:
            return

        logger.warning("Dropping tables in D1...")
        try:
            table_result = await self.d1_master_client.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            existing_tables = [row["name"] for row in table_result.get("results", [])]
            for table_name in existing_tables:
                _ = await self.d1_master_client.execute_query(f"DROP TABLE IF EXISTS {table_name}")
        except Exception as exp:
            logger.warning(f"Could not drop tables in D1: {exp}")

    async def _init_traditional_models(self, drop_all: bool) -> None:
        """Initialize traditional database models."""
        if self.master_engine is None:
            raise DBError("Database not initialized. Call setup first.")

        async with self.master_engine.begin() as conn:
            if drop_all:
                logger.warning("Dropping all tables...")
                await conn.run_sync(SQLModel.metadata.drop_all)

            logger.info("Creating all tables...")
            await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("Tables created successfully.")

    async def init_db_models(self, drop_all: bool = False) -> None:
        """Initialize database models/tables."""
        try:
            if self.is_d1_mode:
                await self._init_d1_models(drop_all)
            else:
                await self._init_traditional_models(drop_all)
        except Exception as exp:
            db_type = "D1" if self.is_d1_mode else "traditional"
            msg = f"Failed to initialize {db_type} database models: {exp}"
            logger.error(msg)
            raise DBError(msg) from exp

    # -----------------------------
    # Plugin interface implementation
    # -----------------------------
    async def setup(self, settings: Settings) -> bool:
        """Initialize database engines and sessionmakers from settings."""
        if not settings.database_url:
            logger.info("Database URL not configured, skipping database setup")
            self.is_ready = True
            return True

        try:
            # Check if this is a D1 connection
            if self._is_d1_url(settings.database_url):
                self.is_d1_mode = True
                self.d1_master_client = self._create_d1_client(settings.database_url)
                logger.info("Master D1 client initialized", extra={"url": settings.database_url})

                # TODO: Support replica D1 database if needed
                # if replica_url and self._is_d1_url(replica_url):
                #     self.d1_replica_client = self._create_d1_client(replica_url)
                #     logger.info("Replica D1 client initialized", extra={"url": replica_url})

            else:
                # Traditional database setup
                self.is_d1_mode = False
                self.master_engine = self._make_engine(
                    settings.database_url,
                    settings.database_pool_size,
                    settings.database_max_overflow,
                    settings.database_echo,
                )
                self.master_session = async_sessionmaker(self.master_engine, class_=DBSession)
                logger.info("Master DB engine initialized", extra={"url": settings.database_url})

                # TODO : Note: replica_url is not in current Settings, but could be added later
                # if replica_url:
                #     self.replica_engine = self._make_engine(replica_url, pool_size, max_overflow, echo)
                #     self.replica_session = async_sessionmaker(self.replica_engine, class_=DBSession)
                #     logger.info("Replica DB engine initialized", extra={"url": replica_url})

            self.is_ready = True
            return True
        except Exception as exp:
            self.is_ready = False
            msg = f"Failed to initialize database: {exp}"
            logger.error(msg)
            return False

    async def teardown(self) -> bool:
        """Dispose database engines to cleanup connections."""
        try:
            if self.is_d1_mode:
                # Close D1 clients
                if self.d1_master_client:
                    await self.d1_master_client.close()
                    logger.info("Master D1 client closed")
                    self.d1_master_client = None
                if self.d1_replica_client:
                    await self.d1_replica_client.close()
                    logger.info("Replica D1 client closed")
                    self.d1_replica_client = None
            else:
                # Dispose traditional database engines
                if self.master_engine:
                    await self.master_engine.dispose()
                    logger.info("Master DB engine disposed")
                    self.master_engine = None
                    self.master_session = None
                if self.replica_engine:
                    await self.replica_engine.dispose()
                    logger.info("Replica DB engine disposed")
                    self.replica_engine = None
                    self.replica_session = None

            self.is_d1_mode = False
            self.is_ready = False
            return True
        except Exception as exp:
            logger.error(f"Failed to dispose database connections: {exp}")
            return False

    async def _check_d1_health(self, results: dict[str, Any]) -> None:
        """Check D1 database health."""
        if self.d1_master_client:
            results["master_schema"] = "d1"
            try:
                # Test D1 connection with simple query
                _ = await self.d1_master_client.execute_query("SELECT 1 as result")
                results["master_response"] = True
            except Exception as exp:
                logger.exception(f"Health check failed for master D1: {exp}")
                results["master_response"] = False
        else:
            results["master_schema"] = None
            results["master_response"] = False

        if self.d1_replica_client:
            results["replica_schema"] = "d1"
            try:
                _ = await self.d1_replica_client.execute_query("SELECT 1 as result")
                results["replica_response"] = True
            except Exception as exp:
                logger.exception(f"Health check failed for replica D1: {exp}")
                results["replica_response"] = False
        else:
            results["replica_schema"] = None
            results["replica_response"] = False

    async def _check_traditional_db_health(self, results: dict[str, Any]) -> None:
        """Check traditional database health."""
        # Check master database
        if self.master_engine:
            master_url = str(self.master_engine.url)
            results["master_schema"] = master_url.split("://")[0] if "://" in master_url else "unknown"

            try:
                async with self.master_engine.connect() as conn:
                    row = await conn.execute(text("SELECT 1 as result"))
                    results["master_response"] = bool(row.scalar_one())
            except Exception as exp:
                logger.exception(f"Health check failed for master DB: {exp}")
                results["master_response"] = False
        else:
            results["master_schema"] = None
            results["master_response"] = False

        # Check replica database
        if self.replica_engine:
            replica_url = str(self.replica_engine.url)
            results["replica_schema"] = replica_url.split("://")[0] if "://" in replica_url else "unknown"

            try:
                async with self.replica_engine.connect() as conn:
                    row = await conn.execute(text("SELECT 1 as result"))
                    results["replica_response"] = bool(row.scalar_one())
            except Exception as exp:
                logger.exception(f"Health check failed for replica DB: {exp}")
                results["replica_response"] = False
        else:
            results["replica_schema"] = None
            results["replica_response"] = False

    async def check_health(self) -> dict[str, Any]:
        """Check database connectivity and return detailed health information."""
        if not self.is_ready:
            return {
                "master_schema": None,
                "replica_schema": None,
                "master_response": False,
                "replica_response": False,
                "is_ready": False,
                "reason": "Plugin not ready",
            }

        results: dict[str, Any] = {"is_ready": self.is_ready}

        if self.is_d1_mode:
            await self._check_d1_health(results)
        else:
            await self._check_traditional_db_health(results)

        return results


################################################################################
# Utility functions
################################################################################
async def get_session(readonly: bool = False) -> _AsyncGeneratorContextManager[DBSession, None]:
    """Get a managed database session."""
    return DatabaseManager.get_instance().get_session(readonly=readonly)


async def get_transaction(readonly: bool = False) -> _AsyncGeneratorContextManager[DBSession, None]:
    """Get a transactional database session."""
    return DatabaseManager.get_instance().get_transaction(readonly=readonly)


def generate_ddl(url: str = "sqlite:///:memory:") -> str:
    """
    Generate the full SQL DDL for all tables defined with SQLModel.
    :param url: SQLAlchemy URL (affects dialect: mysql, postgresql, sqlite, etc.)
    :return: SQL string
    """
    engine = create_engine(url)
    ddl_statements = []

    # Loop through all tables in metadata
    for table in SQLModel.metadata.sorted_tables:
        # Table create statement
        ddl_statements.append(str(CreateTable(table).compile(engine)))

        # Indexes (excluding those automatically created with PK/unique)
        for idx in table.indexes:
            ddl_statements.append(str(CreateIndex(idx).compile(engine)))

    return ";\n\n".join(ddl_statements) + ";"


################################################################################
# Base Repository Class
################################################################################


class BaseRepository(ABC):
    """
    Abstract base repository class that provides common database operations.
    All repository classes should inherit from this to get standard functionality.
    """

    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        """
        Initialize repository with database manager.
        If db_manager is None, uses the singleton instance.
        """
        self.db_manager = db_manager or DatabaseManager.get_instance()
        self._session_factory: Callable[[], DBSession] | None = None

    # Session Management (Abstraction Layer)
    @property
    def session_factory(self) -> Callable[[], DBSession]:
        """Get session factory with lazy initialization."""
        if self._session_factory is None:
            self._session_factory = self.db_manager.get_session_factory()
        return self._session_factory

    @asynccontextmanager
    async def session(self, readonly: bool = False) -> AsyncGenerator[DBSession, None]:
        """
        Get a managed database session.
        Automatically handles session lifecycle and cleanup.
        """
        async with self.db_manager.get_session(readonly=readonly) as session:
            yield session

    @asynccontextmanager
    async def transaction(self, readonly: bool = False) -> AsyncGenerator[DBSession, None]:
        """
        Get a transactional database session.
        Automatically handles transaction commit/rollback.
        """
        async with self.db_manager.get_transaction(readonly=readonly) as session:
            yield session

    # Common Repository Operations
    async def get_by_id(self, entity_class: type[ModelType], entity_id: Any, readonly: bool = True) -> ModelType | None:
        """
        Get entity by ID. Template method for common get operations.
        Override in subclasses for custom logic.
        """
        async with self.session(readonly=readonly) as session:
            return await session.get(entity_class, entity_id)

    async def create(self, entity: ModelType, commit: bool = True) -> ModelType:
        """
        Create a new entity.
        """
        async with self.transaction() as session:
            session.add(entity)
            if commit:
                await session.flush()
            return entity

    async def create_many(self, entities: list[ModelType], commit: bool = True) -> list[ModelType]:
        """
        Create multiple entities in a single transaction.
        """
        async with self.transaction() as session:
            session.add_all(entities)
            if commit:
                await session.flush()
            return entities

    async def update(self, entity: object, commit: bool = True) -> object:
        """
        Update an existing entity.
        """
        async with self.transaction() as session:
            # Entity should be attached to session already or merged
            session.add(entity)
            if commit:
                await session.flush()
            return entity

    async def delete(self, entity: object, commit: bool = True) -> bool:
        """
        Delete an entity.
        """
        try:
            async with self.transaction() as session:
                # If entity is detached, merge it first
                merged_entity = await session.merge(entity)
                await session.delete(merged_entity)
                if commit:
                    await session.flush()
                return True
        except Exception as e:
            logger.error(f"Error deleting entity: {e}")
            return False

    async def soft_delete(
        self, table_name: str, where_conditions: dict[str, Any], session: DBSession | None = None
    ) -> int:
        """
        Perform soft delete on records by setting N_IN_USED=0 and D_UPDATED_AT=now().

        Args:
            table_name: Name of the table to soft delete from
            where_conditions: Dictionary of column-value pairs for WHERE clause
            session: Optional session to use, if None will create a new transaction

        Returns:
            Number of rows affected

        Raises:
            DBError: If database operation fails

        Example:
            >>> await repo.soft_delete("SYS_MAP", {"C_CATEGORY": "old_category"})
            >>> await repo.soft_delete("SYS_DICT", {"C_CATEGORY": "test", "N_KEY": 123})
        """
        if not table_name:
            raise ValueError("Table name cannot be empty")
        if not where_conditions:
            raise ValueError("Where conditions cannot be empty")

        # Build WHERE clause from conditions
        where_parts = []
        params = {}

        for param_counter, (column, value) in enumerate(where_conditions.items()):
            param_name = f"param_{param_counter}"
            where_parts.append(f"{column} = :{param_name}")
            params[param_name] = value

        where_clause = " AND ".join(where_parts)
        params["updated_at"] = datetime.now()

        query = f"UPDATE {table_name} SET N_IN_USED = 0, D_UPDATED_AT = :updated_at WHERE {where_clause}"

        try:
            if session:
                # Use provided session (within existing transaction)
                result = await session.execute(text(query), params)  # pyright: ignore[reportDeprecated]
            else:
                # Use execute_raw_query (creates its own transaction)
                result = await self.db_manager.execute_raw_query(query, params, readonly=False)

            affected_rows = getattr(result, "rowcount", 0)
            return affected_rows
        except Exception as e:
            logger.error(f"Failed to soft delete from {table_name}: {e}")
            raise DBError(f"Failed to soft delete from {table_name}: {e}") from e

    async def execute_query(self, query: Select[Any] | Any, readonly: bool = True) -> Any:
        """
        Execute a custom SQLModel query.
        Uses SQLModel's exec() method for proper type handling.
        """
        async with self.session(readonly=readonly) as session:
            result = await session.exec(query)
            return result

    async def execute_raw_sql(self, sql: str, readonly: bool = True) -> Any:
        """
        Execute raw SQL query.
        """
        return await self.db_manager.execute_raw_query(sql, readonly=readonly)

    # Health and Status
    async def is_connected(self) -> bool:
        """
        Check if database is connected and ready.
        """
        try:
            health = await self.db_manager.check_health()
            return bool(health.get("master", False))
        except Exception:
            return False

    # Template Methods for Subclasses
    @abstractmethod
    async def find_by_criteria(self, criteria: dict[str, Any]) -> list[object]:
        """
        Abstract method for finding entities by criteria.
        Must be implemented by subclasses.
        """

    def configure_session_factory(self, factory: Callable[[], DBSession]) -> None:
        self._session_factory = factory

    # Utility Methods
    def table_name(self, model_class: type[SQLModel]) -> str:
        """
        Get the table name from a SQLModel class.

        Args:
            model_class: The SQLModel class to get table name from

        Returns:
            The table name as defined in the model's __tablename__ attribute

        Raises:
            ValueError: If model doesn't have a __tablename__ attribute

        Example:
            >>> table_name = repo.table_name(SysMap)
            >>> print(table_name)  # "SYS_MAP"
        """
        if not hasattr(model_class, "__tablename__"):
            raise ValueError(f"Model {model_class.__name__} does not have a __tablename__ attribute")
        return cast(str, model_class.__tablename__)
