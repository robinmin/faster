"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


#######################################################################
# Usage sample:
#
# from sqlalchemy.sql import text
# from sqlalchemy.orm import Session
#
# conn = op.get_bind()
#
# # create session based on connection
# session = Session(bind=conn)
#
# # Or, call execute directly with conn
# conn.execute(
#     text("INSERT INTO metadata (key, value) VALUES (:key, :value)"),
#     {"key": key, "value": value},
# )
#######################################################################

def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
