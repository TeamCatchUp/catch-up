"""Add Workflow Studio credential tables

Revision ID: 3b8a1f2c9d0e
Revises: 9ffd82875b6e
Create Date: 2026-05-10 00:00:00.000000

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b8a1f2c9d0e"
down_revision: Union[str, Sequence[str], None] = "9ffd82875b6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workflow_credentials",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("vendor", sa.String(length=32), nullable=False),
        sa.Column("auth_type", sa.String(length=32), nullable=False),
        sa.Column(
            "ownership_type",
            sa.String(length=32),
            server_default="user_personal",
            nullable=False,
            comment="workspace_shared: 전사 공유 / user_personal: 개인 소유",
        ),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True, comment="user_personal Credential 소유자"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True, comment="Credential을 등록한 사용자"),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "external_tenant_id",
            sa.String(length=255),
            nullable=False,
            comment="Slack team_id, Atlassian cloud_id, GitHub installation/account/server 식별자",
        ),
        sa.Column("external_tenant_name", sa.String(length=255), nullable=True),
        sa.Column(
            "external_account_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("external_account_name", sa.String(length=255), nullable=True),
        sa.Column("external_account_email", sa.String(length=255), nullable=True),
        sa.Column(
            "server_url",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="Vendor에서 부여한 OAuth/API 권한 목록",
        ),
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="Runtime에 해당 Credential으로 할 수 있는 행동",
        ),
        sa.Column(
            "encrypted_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="암호화된 access_token, refresh_token, API token, webhook URL 등",
        ),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="vendor별 보조 메타데이터",
        ),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "vendor IN ('github', 'slack', 'atlassian', 'channel_talk')",
            name="ck_workflow_credentials_vendor",
        ),
        sa.CheckConstraint(
            "auth_type IN ("
            "'oauth2_user', "
            "'bot_token', "
            "'app_installation', "
            "'api_token', "
            "'service_account', "
            "'personal_access_token'"
            ")",
            name="ck_workflow_credentials_auth_type",
        ),
        sa.CheckConstraint(
            "ownership_type IN ('workspace_shared', 'user_personal')",
            name="ck_workflow_credentials_ownership_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'needs_reauth', 'expired', 'revoked', 'error')",
            name="ck_workflow_credentials_status",
        ),
        sa.CheckConstraint(
            "("
            "ownership_type = 'user_personal' AND owner_user_id IS NOT NULL"
            ") OR ("
            "ownership_type = 'workspace_shared' AND owner_user_id IS NULL"
            ")",
            name="ck_workflow_credentials_owner_matches_ownership",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_workflow_credentials_workspace_owner_user",
        "workflow_credentials",
        ["workspace_id", "owner_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_credentials_created_by_user_id",
        "workflow_credentials",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "idx_workflow_credentials_workspace_ownership_vendor_status",
        "workflow_credentials",
        ["workspace_id", "ownership_type", "vendor", "status"],
        unique=False,
    )
    op.create_index(
        "uq_workflow_credentials_workspace_shared_identity",
        "workflow_credentials",
        ["vendor", "auth_type", "workspace_id", "external_tenant_id", "external_account_id"],
        unique=True,
        postgresql_where=sa.text("ownership_type = 'workspace_shared'"),
    )
    op.create_index(
        "uq_workflow_credentials_user_personal_identity",
        "workflow_credentials",
        ["vendor", "auth_type", "workspace_id", "owner_user_id", "external_tenant_id", "external_account_id"],
        unique=True,
        postgresql_where=sa.text("ownership_type = 'user_personal'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_workflow_credentials_user_personal_identity", table_name="workflow_credentials")
    op.drop_index("uq_workflow_credentials_workspace_shared_identity", table_name="workflow_credentials")
    op.drop_index("idx_workflow_credentials_workspace_ownership_vendor_status", table_name="workflow_credentials")
    op.drop_index("ix_workflow_credentials_created_by_user_id", table_name="workflow_credentials")
    op.drop_index("idx_workflow_credentials_workspace_owner_user", table_name="workflow_credentials")
    op.drop_table("workflow_credentials")
