"""add github metadata tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "github_pr_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("author_database_id", sa.Integer(), nullable=True),
        sa.Column("assignee_database_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column(
            "requested_reviewer_database_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=True,
        ),
        sa.Column("label_names", postgresql.ARRAY(sa.String(length=255)), nullable=True),
        sa.Column("milestone_title", sa.String(length=255), nullable=True),
        sa.Column("base_ref", sa.String(length=255), nullable=True),
        sa.Column("head_ref", sa.String(length=255), nullable=True),
        sa.Column("draft", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("merged", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("review_decision", sa.String(length=32), nullable=True),
        sa.Column("additions", sa.Integer(), nullable=True),
        sa.Column("deletions", sa.Integer(), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('open', 'closed', 'merged')",
            name="ck_github_pr_metadata_state",
        ),
        sa.CheckConstraint(
            "review_decision IS NULL OR review_decision IN ("
            "'APPROVED', 'CHANGES_REQUESTED', 'REVIEW_REQUIRED', 'UNKNOWN'"
            ")",
            name="ck_github_pr_metadata_review_decision",
        ),
        sa.ForeignKeyConstraint(
            ["author_database_id"],
            ["github_users.database_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_part_id"],
            ["document_parts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["github_repositories.repo_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_part_id",
            name="uq_github_pr_metadata_document_part_id",
        ),
    )
    op.create_index(
        "ix_github_pr_metadata_author_database_id",
        "github_pr_metadata",
        ["author_database_id"],
    )
    op.create_index(
        "ix_github_pr_metadata_document_part_id",
        "github_pr_metadata",
        ["document_part_id"],
    )
    op.create_index(
        "ix_github_pr_metadata_repository_number",
        "github_pr_metadata",
        ["repository_id", "number"],
    )

    op.create_table(
        "github_issue_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("author_database_id", sa.Integer(), nullable=True),
        sa.Column("assignee_database_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("label_names", postgresql.ARRAY(sa.String(length=255)), nullable=True),
        sa.Column("milestone_title", sa.String(length=255), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('open', 'closed')",
            name="ck_github_issue_metadata_state",
        ),
        sa.ForeignKeyConstraint(
            ["author_database_id"],
            ["github_users.database_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_part_id"],
            ["document_parts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["github_repositories.repo_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_part_id",
            name="uq_github_issue_metadata_document_part_id",
        ),
    )
    op.create_index(
        "ix_github_issue_metadata_author_database_id",
        "github_issue_metadata",
        ["author_database_id"],
    )
    op.create_index(
        "ix_github_issue_metadata_document_part_id",
        "github_issue_metadata",
        ["document_part_id"],
    )
    op.create_index(
        "ix_github_issue_metadata_repository_number",
        "github_issue_metadata",
        ["repository_id", "number"],
    )

    op.create_table(
        "github_commit_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("sha", sa.String(length=64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("author_database_id", sa.Integer(), nullable=True),
        sa.Column("committer_database_id", sa.Integer(), nullable=True),
        sa.Column("authored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("additions", sa.Integer(), nullable=True),
        sa.Column("deletions", sa.Integer(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_database_id"],
            ["github_users.database_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["committer_database_id"],
            ["github_users.database_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_part_id"],
            ["document_parts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["github_repositories.repo_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_part_id",
            name="uq_github_commit_metadata_document_part_id",
        ),
    )
    op.create_index(
        "ix_github_commit_metadata_author_database_id",
        "github_commit_metadata",
        ["author_database_id"],
    )
    op.create_index(
        "ix_github_commit_metadata_document_part_id",
        "github_commit_metadata",
        ["document_part_id"],
    )
    op.create_index(
        "ix_github_commit_metadata_repository_sha",
        "github_commit_metadata",
        ["repository_id", "sha"],
    )

    op.create_table(
        "github_comment_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("comment_type", sa.String(length=32), nullable=False),
        sa.Column("comment_id", sa.BigInteger(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_database_id", sa.Integer(), nullable=True),
        sa.Column("issue_number", sa.Integer(), nullable=True),
        sa.Column("pull_number", sa.Integer(), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("original_line", sa.Integer(), nullable=True),
        sa.Column("in_reply_to_comment_id", sa.BigInteger(), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "comment_type IN ('issue_comment', 'pr_review_comment', 'commit_comment')",
            name="ck_github_comment_metadata_comment_type",
        ),
        sa.ForeignKeyConstraint(
            ["author_database_id"],
            ["github_users.database_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_part_id"],
            ["document_parts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["github_repositories.repo_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_part_id",
            name="uq_github_comment_metadata_document_part_id",
        ),
        sa.UniqueConstraint(
            "installation_id",
            "repository_id",
            "comment_type",
            "comment_id",
            name="uq_github_comment_metadata_identity",
        ),
    )
    op.create_index(
        "ix_github_comment_metadata_author_database_id",
        "github_comment_metadata",
        ["author_database_id"],
    )
    op.create_index(
        "ix_github_comment_metadata_document_part_id",
        "github_comment_metadata",
        ["document_part_id"],
    )
    op.create_index(
        "ix_github_comment_metadata_issue",
        "github_comment_metadata",
        ["repository_id", "issue_number"],
    )
    op.create_index(
        "ix_github_comment_metadata_pull",
        "github_comment_metadata",
        ["repository_id", "pull_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_github_comment_metadata_pull", table_name="github_comment_metadata")
    op.drop_index("ix_github_comment_metadata_issue", table_name="github_comment_metadata")
    op.drop_index(
        "ix_github_comment_metadata_document_part_id",
        table_name="github_comment_metadata",
    )
    op.drop_index(
        "ix_github_comment_metadata_author_database_id",
        table_name="github_comment_metadata",
    )
    op.drop_table("github_comment_metadata")

    op.drop_index(
        "ix_github_commit_metadata_repository_sha",
        table_name="github_commit_metadata",
    )
    op.drop_index(
        "ix_github_commit_metadata_document_part_id",
        table_name="github_commit_metadata",
    )
    op.drop_index(
        "ix_github_commit_metadata_author_database_id",
        table_name="github_commit_metadata",
    )
    op.drop_table("github_commit_metadata")

    op.drop_index(
        "ix_github_issue_metadata_repository_number",
        table_name="github_issue_metadata",
    )
    op.drop_index(
        "ix_github_issue_metadata_document_part_id",
        table_name="github_issue_metadata",
    )
    op.drop_index(
        "ix_github_issue_metadata_author_database_id",
        table_name="github_issue_metadata",
    )
    op.drop_table("github_issue_metadata")

    op.drop_index(
        "ix_github_pr_metadata_repository_number",
        table_name="github_pr_metadata",
    )
    op.drop_index(
        "ix_github_pr_metadata_document_part_id",
        table_name="github_pr_metadata",
    )
    op.drop_index(
        "ix_github_pr_metadata_author_database_id",
        table_name="github_pr_metadata",
    )
    op.drop_table("github_pr_metadata")
