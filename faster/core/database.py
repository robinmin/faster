from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from .exceptions import DBError
from .logger import get_logger

logger = get_logger(__name__)


class EngineKwargs(TypedDict, total=False):
    echo: bool
    future: bool
    connect_args: dict[str, bool]
    pool_size: int
    max_overflow: int


class DatabaseManager:
    def __init__(self) -> None:
        self.master_engine: AsyncEngine | None = None
        self.replica_engine: AsyncEngine | None = None
        self.master_session: async_sessionmaker[AsyncSession] | None = None
        self.replica_session: async_sessionmaker[AsyncSession] | None = None

    def _make_engine(self, url: str, pool_size: int, max_overflow: int, echo: bool) -> AsyncEngine:
        engine_kwargs: EngineKwargs = {"echo": echo, "future": True}

        if url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs["pool_size"] = pool_size
            engine_kwargs["max_overflow"] = max_overflow

        return create_async_engine(url, **engine_kwargs)

    async def setup(
        self,
        master_url: str,
        pool_size: int = 10,
        max_overflow: int = 20,
        echo: bool = False,
        replica_url: str | None = None,
    ) -> None:
        """Initialize engines and sessionmakers."""
        try:
            self.master_engine = self._make_engine(master_url, pool_size, max_overflow, echo)
            self.master_session = async_sessionmaker(self.master_engine, class_=AsyncSession)
            logger.info("Master DB engine initialized", extra={"url": master_url})

            if replica_url:
                self.replica_engine = self._make_engine(replica_url, pool_size, max_overflow, echo)
                self.replica_session = async_sessionmaker(self.replica_engine, class_=AsyncSession)
                logger.info("Replica DB engine initialized", extra={"url": replica_url})

        except Exception as exp:
            msg = f"Failed to initialize database engines: {exp}"
            logger.error(msg)
            raise DBError(msg) from exp

    async def close(self) -> None:
        """Dispose master and replica engines to cleanup connections."""
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

    # -----------------------------
    # FastAPI dependency
    # -----------------------------
    async def get_raw_session(self, readonly: bool = False) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a FastAPI dependency session. Please note that this session is not managed by the database engine. That means you need to close it manually. Carefully handle exceptions and errors.
        Example:
        @app.get("/users")
            async def get_users(db: AsyncSession = Depends(get_raw_session)):
                query = select(User)
                return await db.execute(query).scalars().all()
        """
        session_factory = self.replica_session if readonly and self.replica_session else self.master_session
        if session_factory is None:
            raise DBError("Database not initialized. Call setup first.")

        session = session_factory()
        try:
            yield session
        finally:
            await session.close()

    # -----------------------------
    # Transaction manager
    # -----------------------------
    @asynccontextmanager
    async def get_txn(self, readonly: bool = False) -> AsyncGenerator[AsyncSession, None]:
        """
        FastAPI dependency transaction.
        Example:
            async def get_users(txn: AsyncSession = Depends(get_txn)):
                # Check if user already exists
                existing_user = await txn.exec(select(User).where(User.email == user_data.email))
                if existing_user.first():
                    # If you raise an exception here, the transaction will be automatically rolled back.
                    raise HTTPException(status_code=400, detail="Email already registered")
        """
        session_factory = self.replica_session if readonly and self.replica_session else self.master_session
        if session_factory is None:
            raise DBError("Database not initialized. Call setup first.")

        session = session_factory()
        try:
            async with session.begin():
                yield session
        except Exception as exp:
            # We just log the exception and re-raise it as a DBError.
            msg = f"Transaction failed: {exp}"
            logger.error(msg)
            raise DBError(msg) from exp
        finally:
            await session.close()

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

    async def check_health(self) -> dict[str, bool]:
        """Check connectivity by running 'SELECT 1 as result' on master and replica (if available)."""
        results: dict[str, bool] = {}
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
            logger.exception(f"Health check failed for replica DB : {exp}")
            results["replica"] = False

        return results


# Singleton instance of DatabaseManager
db_mgr = DatabaseManager()


################################################################################
# Utility functions
################################################################################
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
