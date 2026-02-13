"""Add server default to joined_at

Revision ID: 68c7d0ba43b6
Revises: 8eef883d4c43
Create Date: 2026-02-13 16:22:21.938107

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68c7d0ba43b6'
down_revision: Union[str, Sequence[str], None] = '8eef883d4c43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('user_workspaces', 'joined_at',
               existing_type=sa.DateTime(timezone=True),
               server_default=sa.func.now(),
               existing_nullable=False)

def downgrade() -> None:
    op.alter_column('user_workspaces', 'joined_at',
               existing_type=sa.DateTime(timezone=True),
               server_default=None,
               existing_nullable=False)
