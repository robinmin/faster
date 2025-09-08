from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager  # pyright: ignore[reportPrivateUsage]
from datetime import datetime
from typing import Any, TypedDict, TypeVar, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import Select
from typing_extensions import Self

from .config import Settings
from .exceptions import DBError
from .logger import get_logger
from .plugins import BasePlugin

###############################################################################

logger = get_logger(__name__)

# Type definitions - Simplified using SQLModel's native types
ModelType = TypeVar("ModelType", bound=SQLModel)
DBSession = AsyncSession

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
    """

    _instance = None

    def __init__(self) -> None:
        self.master_engine: AsyncEngine | None = None
        self.replica_engine: AsyncEngine | None = None
        self.master_session: async_sessionmaker[DBSession] | None = None
        self.replica_session: async_sessionmaker[DBSession] | None = None
        self.is_ready: bool = False

    @classmethod
    def get_instance(cls) -> Self:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _make_engine(self, url: str, pool_size: int, max_overflow: int, echo: bool) -> AsyncEngine:
        engine_kwargs: EngineKwargs = {"echo": echo, "future": True}

        if url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs["pool_size"] = pool_size
            engine_kwargs["max_overflow"] = max_overflow

        return create_async_engine(url, **engine_kwargs)

    def get_session_factory(self, readonly: bool = False) -> Callable[[], DBSession]:
        """Get an async session factory function for dependency injection."""
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
        async with self.get_session(readonly=readonly) as session:
            # Use execute() for raw SQL text as exec() doesn't support TextClause
            result = await session.execute(text(query), params or {}) # pyright: ignore[reportDeprecated]
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

    # Backward compatibility aliases
    async def get_raw_session(self, readonly: bool = False) -> _AsyncGeneratorContextManager[DBSession, None]:
        """Deprecated: Use get_session() instead."""
        return self.get_session(readonly=readonly)

    async def get_txn(self, readonly: bool = False) -> _AsyncGeneratorContextManager[DBSession, None]:
        """Deprecated: Use get_transaction() instead."""
        return self.get_transaction(readonly=readonly)

    # -----------------------------
    # Init models
    # -----------------------------
    async def init_db_models(self, drop_all: bool = False) -> None:
        if self.master_engine is None:
            raise DBError("Database not initialized. Call setup first.")

        async with self.master_engine.begin() as conn:
            try:
                if drop_all:
                    logger.warning("Dropping all tables...")
                    await conn.run_sync(SQLModel.metadata.drop_all)

                logger.info("Creating all tables...")
                await conn.run_sync(SQLModel.metadata.create_all)
                logger.info("Tables created successfully.")
            except Exception as exp:
                msg = f"Failed to initialize database models: {exp}"
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
            msg = f"Failed to initialize database engines: {exp}"
            logger.error(msg)
            return False

    async def teardown(self) -> bool:
        """Dispose database engines to cleanup connections."""
        try:
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
            self.is_ready = False
            return True
        except Exception as exp:
            logger.error(f"Failed to dispose database engines: {exp}")
            return False

    async def check_health(self) -> dict[str, Any]:
        """Check database connectivity by running 'SELECT 1' on master and replica (if available)."""
        if not self.is_ready:
            return {"master": False, "replica": False, "reason": "Plugin not ready"}

        results: dict[str, Any] = {}
        try:
            if self.master_engine:
                async with self.master_engine.connect() as conn:
                    row = await conn.execute(text("SELECT 1 as result"))
                    results["master"] = bool(row.scalar_one())
            else:
                results["master"] = False
        except Exception as exp:
            logger.exception(f"Health check failed for master DB: {exp}")
            results["master"] = False

        try:
            if self.replica_engine:
                async with self.replica_engine.connect() as conn:
                    row = await conn.execute(text("SELECT 1 as result"))
                    results["replica"] = bool(row.scalar_one())
            else:
                results["replica"] = False
        except Exception as exp:
            logger.exception(f"Health check failed for replica DB: {exp}")
            results["replica"] = False

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


# Backward compatibility
async def get_raw_session(readonly: bool = False) -> _AsyncGeneratorContextManager[DBSession, None]:
    """Deprecated: Use get_session() instead."""
    return DatabaseManager.get_instance().get_session(readonly=readonly)


async def get_txn(readonly: bool = False) -> _AsyncGeneratorContextManager[DBSession, None]:
    """Deprecated: Use get_transaction() instead."""
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

    async def soft_delete(self, table_name: str, where_conditions: dict[str, Any], session: DBSession | None = None) -> int:
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
                result = await session.execute(text(query), params) # pyright: ignore[reportDeprecated]
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
        if not hasattr(model_class, '__tablename__'):
            raise ValueError(f"Model {model_class.__name__} does not have a __tablename__ attribute")
        return cast(str, model_class.__tablename__)
