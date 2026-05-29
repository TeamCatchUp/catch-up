"""add agent trigger outbox

Revision ID: 8d12f3a4b5c6
Revises: 4c91f2a8e6b3
Create Date: 2026-05-29 21:10:00.000000

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d12f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "4c91f2a8e6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the trigger-run execution fields and transactional dispatch outbox."""
    # Nullable so existing trigger runs remain valid. Workers populate it only
    # after they are about to call ExecutionService.run().
    op.add_column(
        "agent_trigger_runs",
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_agent_trigger_runs_immediate_trigger_event",
        "agent_trigger_runs",
        ["trigger_id", "latest_event_id"],
        unique=True,
        # Immediate triggers dedupe by event. Debounced triggers are excluded
        # because their active row is updated/reset instead of recreated.
        postgresql_where=sa.text("policy_kind = 'immediate'"),
    )
    # The outbox is the durable handoff between webhook ingress and Redis
    # dispatch. It stores only the small routing snapshot needed to publish and
    # recover work; AgentTriggerRun remains the full execution source of truth.
    op.create_table(
        "agent_trigger_outbox",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("trigger_id", sa.BigInteger(), nullable=False),
        sa.Column("agent_spec_id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("stream_message_id", sa.String(length=64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'publishing', 'published', 'failed')",
            name="ck_agent_trigger_outbox_status",
        ),
        sa.ForeignKeyConstraint(
            ["agent_spec_id"],
            ["agent_specs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_trigger_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trigger_id"],
            ["agent_triggers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_agent_trigger_outbox_run_id"),
    )
    op.create_index(
        "idx_agent_trigger_outbox_status_created_at",
        "agent_trigger_outbox",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_agent_trigger_outbox_stream_message_id",
        "agent_trigger_outbox",
        ["stream_message_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the outbox and execution fields added by this revision."""
    # Drop dependent indexes/table first so downgrade does not leave publisher
    # state behind. Existing run history keeps its pre-revision columns only.
    op.drop_index(
        "idx_agent_trigger_outbox_stream_message_id",
        table_name="agent_trigger_outbox",
    )
    op.drop_index(
        "idx_agent_trigger_outbox_status_created_at",
        table_name="agent_trigger_outbox",
    )
    op.drop_table("agent_trigger_outbox")
    op.drop_index(
        "uq_agent_trigger_runs_immediate_trigger_event",
        table_name="agent_trigger_runs",
        postgresql_where=sa.text("policy_kind = 'immediate'"),
    )
    op.drop_column("agent_trigger_runs", "execution_started_at")
