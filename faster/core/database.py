from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
import logging
from typing import Any, TypeVar

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)
# Type variable for generic models
T = TypeVar("T", bound=SQLModel)


def is_sqlite_db(database_url: str | None) -> bool:
    """Check if the database URL is for SQLite."""
    return database_url.startswith("sqlite") if database_url else False


class DatabaseManager:
    """Database connection manager."""

    def __init__(self) -> None:
        self.async_engine: AsyncEngine | None = None
        self.AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

    async def initialize(
        self,
        database_url: str | None = None,
        database_pool_size: int = 20,
        database_max_overflow: int = 0,
        database_echo: bool = False,
        is_debug: bool = False,
    ) -> None:
        """Initialize the database connection."""
        engine_kwargs: dict[str, Any] = {
            "echo": database_echo,
            "pool_pre_ping": True,
        }

        # Only apply pool settings if not using in-memory SQLite
        if not is_sqlite_db(database_url):
            engine_kwargs["pool_size"] = database_pool_size
            engine_kwargs["max_overflow"] = database_max_overflow

        if database_url is None:
            raise ValueError("Database URL cannot be None during initialization.")
        self.async_engine = create_async_engine(database_url, **engine_kwargs)

        self.AsyncSessionLocal = async_sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # Create all tables (development environment)
        if is_debug:
            if self.async_engine is None:
                raise RuntimeError("Database engine not initialized.")
            async with self.async_engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("Database tables created in debug mode.")

    async def close(self) -> None:
        """Close the database connection."""
        if self.async_engine:
            await self.async_engine.dispose()
            logger.info("Database connection closed.")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session context."""
        if self.AsyncSessionLocal is None:
            raise RuntimeError("Database session factory not initialized.")
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """Transaction context manager."""
        if self.AsyncSessionLocal is None:
            raise RuntimeError("Database session factory not initialized.")
        async with self.AsyncSessionLocal() as session, session.begin():
            yield session

    async def read(self, model: type[T], **kwargs: Any) -> list[T] | None:
        """Execute a read-only query using the internal session."""
        async with self.get_session() as session:
            try:
                statement = select(model).filter_by(**kwargs)
                compiled_sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
                logger.debug(f"[SQL] <--: {compiled_sql}")
                results = await session.exec(statement)
                return list(results)
            except Exception as e:
                logger.error(
                    f"Error during db_read for model {model.__name__} with filters {kwargs}: {e}",
                    exc_info=True,
                )
            return None

    async def write(self, instance: T) -> bool:
        """Execute a write operation (add or update) using the internal session."""
        async with self.get_session() as session:
            result = True
            try:
                session.add(instance)
                instance_state = inspect(instance)
                assert instance_state is not None
                operation_type = "insert" if instance_state.pending else "update"
                pk_value = instance_state.identity
                logger.debug(
                    f"Executing db_write ({operation_type}) for instance {instance.__class__.__name__} (PK: {pk_value})"
                )

                await session.commit()
                await session.refresh(instance)
                logger.debug(
                    f"db_write successful for instance {instance.__class__.__name__} (PK: {instance_state.identity})"
                )
            except Exception as e:
                await session.rollback()
                logger.error(
                    f"Error during db_write for instance {instance.__class__.__name__}: {e}",
                    exc_info=True,
                )
                result = False
            return result


database_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session."""
    async with database_manager.get_session() as session:
        yield session


async def db_transaction(session: AsyncSession, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Execute a function within a database transaction."""
    async with database_manager.transaction() as tx_session:
        result = await func(tx_session, *args, **kwargs)
        return result


async def db_read(model: type[T], filters: dict[str, Any] | None = None, **kwargs: Any) -> list[T] | None:
    """Read data from the database using the internal session."""
    if filters is None:
        filters = {}
    filters.update(kwargs)
    return await database_manager.read(model, **filters)


async def db_write(instance: T) -> bool:
    """Write data to the database using the internal session."""
    return await database_manager.write(instance)


async def health_check() -> bool:
    """Perform a database health check by executing a simple query."""
    if database_manager.async_engine is None:
        logger.warning("Database engine not initialized for health check.")
        return False
    try:
        async with database_manager.async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database health check successful.")
        return True
    except OperationalError as e:
        logger.error(f"Database health check failed: {e}")
        return False
