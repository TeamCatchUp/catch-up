"""allow multiple channel talk document spaces per channel

Revision ID: 4d2f9a8b7c6e
Revises: 03e3080a656c
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d2f9a8b7c6e"
down_revision: Union[str, Sequence[str], None] = "03e3080a656c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_channel_talk_document_credentials_channel_id",
        "channel_talk_document_credentials",
        type_="unique",
    )
    op.create_index(
        "idx_channel_talk_document_credentials_channel_id",
        "channel_talk_document_credentials",
        ["channel_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_channel_talk_document_credentials_channel_id",
        table_name="channel_talk_document_credentials",
    )
    op.create_unique_constraint(
        "uq_channel_talk_document_credentials_channel_id",
        "channel_talk_document_credentials",
        ["channel_id"],
    )
