"""rename channel talk manager role to role_id

Revision ID: 7a1c5f0e2d4b
Revises: 5c12b0994a83
Create Date: 2026-04-20 10:30:00.000000

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "7a1c5f0e2d4b"
down_revision: Union[str, Sequence[str], None] = "5c12b0994a83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "channel_talk_managers",
        "role",
        new_column_name="role_id",
        existing_type=sa.String(length=50),
        existing_nullable=True,
        existing_comment="Manager role such as owner or member",
        comment="Manager role ID returned by Channel Talk",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "channel_talk_managers",
        "role_id",
        new_column_name="role",
        existing_type=sa.String(length=50),
        existing_nullable=True,
        existing_comment="Manager role ID returned by Channel Talk",
        comment="Manager role such as owner or member",
    )
