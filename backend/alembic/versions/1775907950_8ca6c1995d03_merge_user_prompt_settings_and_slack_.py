"""merge user prompt settings and slack lease heads

Revision ID: 8ca6c1995d03
Revises: a5e040dfd8b7, a8f4d4f2b7c1
Create Date: 2026-04-11 20:45:50.900908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ca6c1995d03'
down_revision: Union[str, Sequence[str], None] = ('a5e040dfd8b7', 'a8f4d4f2b7c1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
