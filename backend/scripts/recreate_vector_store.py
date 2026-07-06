from __future__ import annotations

import asyncio

from sqlalchemy import text

from catchup.components.vector_db.v2.constants import VECTOR_STORE_TABLE_NAME
from catchup.db.async_engine import async_engine


async def _drop_existing_tables() -> None:
    async with async_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS knowledge_store CASCADE"))
        await conn.execute(text(f"DROP TABLE IF EXISTS {VECTOR_STORE_TABLE_NAME}"))


async def _main() -> None:
    await _drop_existing_tables()
    await async_engine.dispose()
    print(f"{VECTOR_STORE_TABLE_NAME} dropped")


if __name__ == "__main__":
    asyncio.run(_main())
