from __future__ import annotations

from collections.abc import Iterable
from logging.config import fileConfig
import re
from typing import Any

from alembic import context
from alembic.runtime.migration import MigrationContext
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

# import sqlalchemy as sa

# Alembic Config object
config = context.config

# Logging configuration from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Import your models here so Alembic can detect them
# We need to import all models that inherit from SQLModel
try:
    # Import all models for Alembic auto-detection
    import faster.core.auth.schemas  # type: ignore[unused-ignore]
    import faster.core.schemas  # noqa: F401  # type: ignore[unused-ignore]
except ImportError as e:
    print(f"Warning: Could not import models: {e}")

# Target metadata for 'autogenerate'
target_metadata = SQLModel.metadata

# --------------------- Post-process migration scripts -----------------------
def process_revision_directives(
    context: MigrationContext,
    revision: str | Iterable[str | None] | Iterable[str],
    directives: list[Any],
) -> None:
    """
    Optional: rewrite generated migration scripts.
    You can use sed later to replace AutoString -> sa.String.
    """
    if not directives:
        return

    script = directives[0]
    doc: str = getattr(script, "doc", "")

    # This is optional, won't break anything even if empty
    doc = re.sub(
        r"sqlmodel\.sql\.sqltypes\.AutoString",
        "sa.String",
        doc,
    )

    script.doc = doc

# --------------------- Migration runners ------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in offline mode (no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    if url is None:
        raise ValueError("sqlalchemy.url not found in configuration")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode (with DB connection)."""
    connectable: Engine = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
        )
        with context.begin_transaction():
            context.run_migrations()


# --------------------- Entrypoint -------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
