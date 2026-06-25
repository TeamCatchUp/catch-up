"""add agent trigger definition upsert constraint

Revision ID: 2a7f83bc9d10
Revises: 79d57733f8c0
Create Date: 2026-05-28 19:48:22.000000

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a7f83bc9d10"
down_revision: Union[str, Sequence[str], None] = "79d57733f8c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                """
            SELECT 1
            FROM agent_triggers
            GROUP BY agent_spec_id, source, event_type
            HAVING COUNT(*) > 1
            LIMIT 1
            """
            )
        )
        .first()
    )
    if duplicate is not None:
        raise RuntimeError(
            "Cannot add uq_agent_triggers_agent_spec_source_event_type while "
            "duplicate agent trigger definitions exist"
        )

    op.create_unique_constraint(
        "uq_agent_triggers_agent_spec_source_event_type",
        "agent_triggers",
        ["agent_spec_id", "source", "event_type"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_agent_triggers_agent_spec_source_event_type",
        "agent_triggers",
        type_="unique",
    )
