"""cmetadata 관련 index 추가

Revision ID: 9c522fb79518
Revises: 
Create Date: 2026-02-28 05:00:07.656451

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c522fb79518'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_bigm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_cmetadata_source
        ON langchain_pg_embedding ((cmetadata ->> 'source'))
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_cmetadata_updated_at
        ON langchain_pg_embedding ((cmetadata ->> 'updated_at'))
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_cmetadata_created_at
        ON langchain_pg_embedding ((cmetadata ->> 'created_at'))
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_fts_korean_bigm 
        ON langchain_pg_embedding USING GIN (document gin_bigm_ops)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_cmetadata_source")
    op.execute("DROP INDEX IF EXISTS idx_cmetadata_updated_at")
    op.execute("DROP INDEX IF EXISTS idx_cmetadata_created_at")
    op.execute("DROP INDEX IF EXISTS idx_fts_korean_bigm")
