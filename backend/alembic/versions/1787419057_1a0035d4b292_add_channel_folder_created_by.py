"""add channel folder created_by

Revision ID: 1a0035d4b292
Revises: eee5acf7ee4f
Create Date: 2026-08-23 02:17:37.766254

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1a0035d4b292'
down_revision: Union[str, Sequence[str], None] = 'eee5acf7ee4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FOLDERS_TABLE = "channel_folders"
CREATED_BY_FK = "fk_channel_folders_created_by"

# downgrade가 지우게 될 데이터를 세는 식이다. created_by가 채워진 폴더는
# 컬럼을 없애는 순간 만든 사람을 잃는다.
COUNT_QUERIES: dict[str, str] = {
    "작성자가 기록된 폴더": (
        f"SELECT count(*) FROM {FOLDERS_TABLE} WHERE created_by IS NOT NULL"
    ),
}


def upgrade() -> None:
    """폴더를 만든 사람을 담을 컬럼을 더한다.

    nullable로 둔다. 이 컬럼이 생기기 전에 만들어진 폴더는 만든 사람을
    되찾을 방법이 없어, NOT NULL로 두면 채울 값이 없다.

    인덱스는 걸지 않는다. 이 컬럼으로 폴더를 찾는 자리가 없고, 화면은
    폴더를 먼저 읽은 뒤 그 값으로 사용자를 조회한다.
    """
    op.add_column(
        FOLDERS_TABLE,
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        CREATED_BY_FK,
        FOLDERS_TABLE,
        "users",
        ["created_by"],
        ["id"],
    )


def _refuse_if_creator_data_exists() -> None:
    """작성자가 기록된 폴더가 있으면 downgrade를 중단한다.

    이 컬럼을 없애면 그 값은 다른 어디에도 남지 않는다. 데이터를 지우는
    판단은 마이그레이션이 아니라 사람이 한다.

    alembic은 마이그레이션을 트랜잭션 안에서 돌리므로, 여기서 예외를
    던지면 앞선 DDL을 포함해 아무것도 commit되지 않는다.
    """
    bind = op.get_bind()
    found = []
    for label, query in COUNT_QUERIES.items():
        count = bind.execute(sa.text(query)).scalar()
        if count:
            found.append(f"{label} {count}건")
    if found:
        raise RuntimeError(
            f"{', '.join(found)}이(가) 남아 있어 downgrade를 중단한다."
            " 이 값은 컬럼과 함께 사라진다."
            " 해당 값을 직접 비운 뒤 downgrade를 다시 실행하라."
        )


def downgrade() -> None:
    """작성자 컬럼을 없앤다. 기록된 작성자가 있으면 거부한다."""
    _refuse_if_creator_data_exists()

    op.drop_constraint(CREATED_BY_FK, FOLDERS_TABLE, type_="foreignkey")
    op.drop_column(FOLDERS_TABLE, "created_by")
