# catchup/test/bench.py
import asyncio
import time

import psycopg

from catchup.configs.config import settings

K = 10


async def get_ids(conn: psycopg.AsyncConnection, sql: str) -> set[int]:
    cur = await conn.execute(sql)
    rows = await cur.fetchall()
    return set(int(row[0]) for row in rows)


async def main():
    ef_search_values = [20, 40, 80, 200]
    m = 16
    ef_construction = 64
    table = "hnsw_bench.vecs"
    results = []

    db_url = settings.sqlalchemy_database_url.replace(
        f"{settings.DB_DIALECT}+{settings.DB_DRIVER}",
        settings.DB_DIALECT,
    )

    async with await psycopg.AsyncConnection.connect(db_url, autocommit=True) as conn:

        # 쿼리 벡터: 실제 임베딩 중 하나 (OFFSET 100)
        cur = await conn.execute(f"SELECT embedding FROM {table} LIMIT 1 OFFSET 100")
        row = await cur.fetchone()
        q_str = str(row[0])

        # SeqScan → ground truth
        await conn.execute("SET enable_indexscan = off")
        await conn.execute("SET enable_bitmapscan = off")
        start = time.perf_counter()
        true_ids = await get_ids(
            conn,
            f"SELECT id FROM {table} ORDER BY embedding <=> '{q_str}'::vector LIMIT {K}",
        )
        t_seq = time.perf_counter() - start
        print(f"SeqScan: {t_seq * 1000:.1f}ms")
        print(f"true_ids: {sorted(true_ids)}")
        await conn.execute("SET enable_indexscan = on")
        await conn.execute("SET enable_bitmapscan = on")

        # HNSW 인덱스 빌드
        await conn.execute("DROP INDEX IF EXISTS hnsw_bench.vecs_idx")
        print("HNSW 인덱스 빌드 중...")
        start = time.perf_counter()
        await conn.execute(
            f"CREATE INDEX vecs_idx ON {table} "
            f"USING hnsw(embedding vector_cosine_ops) "
            f"WITH (m={m}, ef_construction={ef_construction})"
        )
        build_time = time.perf_counter() - start
        print(f"HNSW build_time: {build_time:.1f}s")

        # HNSW 검색 + recall
        for ef in ef_search_values:
            await conn.execute(f"SET hnsw.ef_search = {ef}")

            start = time.perf_counter()
            hnsw_ids = await get_ids(
                conn,
                f"SELECT id FROM {table} ORDER BY embedding <=> '{q_str}'::vector LIMIT {K}",
            )
            t_hnsw = time.perf_counter() - start
            print(f"HNSW ef_search={ef}: {t_hnsw * 1000:.1f}ms")
            print(f"hnsw_ids ef_search={ef}: {sorted(hnsw_ids)}")

            recall = len(true_ids & hnsw_ids) / K
            print(f"recall@{K} ef_search={ef}: {recall:.2f} ({len(true_ids & hnsw_ids)}/{K})")

            results.append({
                "data_size": "3.5K (real)",
                "ef_search": ef,
                "build_time_s": round(build_time, 2),
                "hnsw_search_ms": round(t_hnsw * 1000, 1),
                "seqscan_ms": round(t_seq * 1000, 1),
                "recall": recall,
            })

    print("\n=== Summary ===")
    for r in results:
        print(r)


if __name__ == "__main__":
    asyncio.run(main())