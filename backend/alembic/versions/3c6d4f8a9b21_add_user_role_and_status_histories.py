"""Add user role and status histories

Revision ID: 3c6d4f8a9b21
Revises: 95e7a47233a9
Create Date: 2026-03-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c6d4f8a9b21"
down_revision: Union[str, Sequence[str], None] = "95e7a47233a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    op.create_table(
        "user_role_histories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_role", sa.String(length=20), nullable=False),
        sa.Column("after_role", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_user_role_histories_user_created_at",
        "user_role_histories",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "user_status_histories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_status", sa.String(length=20), nullable=False),
        sa.Column("after_status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_user_status_histories_user_created_at",
        "user_status_histories",
        ["user_id", "created_at"],
        unique=False,
    )

    if inspector.has_table("inactive_users"):
        bind.execute(
            sa.text(
                """
                INSERT INTO user_status_histories (
                    user_id,
                    actor_user_id,
                    action,
                    reason,
                    before_status,
                    after_status,
                    created_at
                )
                SELECT
                    user_id,
                    COALESCE(admin_id, user_id),
                    'deactivate',
                    reason,
                    'active',
                    'inactive',
                    deactivated_at
                FROM inactive_users
                """
            )
        )
        indexes = {index["name"] for index in inspector.get_indexes("inactive_users")}
        if "idx_inactive_users_user_id" in indexes:
            op.drop_index("idx_inactive_users_user_id", table_name="inactive_users")
        op.drop_table("inactive_users")


def downgrade() -> None:
    op.create_table(
        "inactive_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reactivated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "deactivated_at", name="uq_inactive_user_timestamp"),
    )
    op.create_index("idx_inactive_users_user_id", "inactive_users", ["user_id"], unique=False)
    op.drop_index("idx_user_status_histories_user_created_at", table_name="user_status_histories")
    op.drop_table("user_status_histories")
    op.drop_index("idx_user_role_histories_user_created_at", table_name="user_role_histories")
    op.drop_table("user_role_histories")
