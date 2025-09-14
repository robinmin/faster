"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""

from collections.abc import Sequence
import logging
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
## import sqlmodel


${imports if imports else ""}

logger = logging.getLogger(__name__)

# Revision identifiers, used by Alembic.
revision: str = "${up_revision}"
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Apply schema changes.

    Example:
        op.create_table(
            "user",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String, nullable=False),
        )
    """
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Revert schema changes.

    Example:
        op.drop_table("user")
    """
    ${downgrades if downgrades else "pass"}
