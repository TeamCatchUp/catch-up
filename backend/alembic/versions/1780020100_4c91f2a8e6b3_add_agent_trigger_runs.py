"""add agent trigger runs

Revision ID: 4c91f2a8e6b3
Revises: 2a7f83bc9d10
Create Date: 2026-05-29 12:00:00.000000

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c91f2a8e6b3"
down_revision: Union[str, Sequence[str], None] = "2a7f83bc9d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agent_trigger_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trigger_id", sa.BigInteger(), nullable=False),
        sa.Column("policy_kind", sa.String(length=30), nullable=False),
        sa.Column("entity_key", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_event_id", sa.String(length=255), nullable=False),
        sa.Column("latest_event_id", sa.String(length=255), nullable=False),
        sa.Column("dispatch_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "policy_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["trigger_id"],
            ["agent_triggers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_agent_trigger_runs_due",
        "agent_trigger_runs",
        ["status", "run_after"],
        unique=False,
    )
    op.create_index(
        "idx_agent_trigger_runs_trigger_latest_event",
        "agent_trigger_runs",
        ["trigger_id", "latest_event_id"],
        unique=False,
    )
    op.create_index(
        "uq_agent_trigger_runs_active_trigger_entity",
        "agent_trigger_runs",
        ["trigger_id", "entity_key"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending', 'dispatching') AND entity_key IS NOT NULL"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_agent_trigger_runs_active_trigger_entity",
        table_name="agent_trigger_runs",
        postgresql_where=sa.text(
            "status IN ('pending', 'dispatching') AND entity_key IS NOT NULL"
        ),
    )
    op.drop_index(
        "idx_agent_trigger_runs_trigger_latest_event",
        table_name="agent_trigger_runs",
    )
    op.drop_index("idx_agent_trigger_runs_due", table_name="agent_trigger_runs")
    op.drop_table("agent_trigger_runs")
