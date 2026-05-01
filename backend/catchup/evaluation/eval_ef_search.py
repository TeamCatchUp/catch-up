"""
hnsw.ef_search 트레이드오프 측정

K=100 (프로덕션 hybrid_search 매칭) 기준으로 ef_search 값별 latency/recall 곡선을 측정한다.
- Ground truth: enable_indexscan=off로 강제한 Seq Scan 결과 top-K
- 비교: SET hnsw.ef_search = X 후 동일 쿼리 top-K
- recall = |seq_topK ∩ hnsw_topK| / K

실행 방법:
    cd backend
    python -m catchup.evaluation.eval_ef_search

전제:
    - 로컬 DB에 idx_embedding_hnsw 인덱스가 존재해야 함
      (PGVECTOR_HNSW_INDEX_ENABLED=True 후 ensure_vector_index() 1회 실행)
    - .env에 DB 접속 + AWS Bedrock 임베딩 자격증명 셋업
"""

import math
import os
import statistics
import sys
import time

import psycopg
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.configs.config import settings

DIMS = settings.PGVECTOR_EMBEDDING_DIMENSIONS
K = 100  # 프로덕션 hybrid_search의 max(100, k+offset)에 매칭
REPEATS = 3  # 쿼리당 반복 측정 횟수
EF_SEARCH_VALUES = [40, 80, 100, 150, 200, 300]

TEST_QUERIES = [
    "어제 오늘까지 해서 Slack Bot 구현된 내용 보여줘",
    "가장 최근 PR 내용 찾아줘",
    "최근에 감사로그 컬럼 정리된 문서 어디있더라?",
    "에이전트 스튜디오 관련 기획 문서 찾아줘",
    "디자인 qa 진행상황을 알려줘",
]


def to_vec_literal(embedding: list[float]) -> str:
    return f"[{','.join(str(v) for v in embedding)}]"


def fetch_seq_truth(
    conn: psycopg.Connection,
    vec_literal: str,
) -> list[str]:
    """Seq Scan 강제 후 top-K id 목록을 ground truth로 반환."""
    collection_name = settings.PGVECTOR_COLLECTION_NAME
    sql = f"""
        SELECT e.id::text
        FROM langchain_pg_embedding e
        JOIN langchain_pg_collection c ON e.collection_id = c.uuid
        WHERE c.name = %(collection_name)s
        ORDER BY (e.embedding::vector({DIMS})) <=> %(vec)s::vector({DIMS})
        LIMIT %(k)s
    """
    with conn.cursor() as cur:
        cur.execute("SET LOCAL enable_indexscan = off")
        cur.execute("SET LOCAL enable_bitmapscan = off")
        cur.execute(sql, {"collection_name": collection_name, "vec": vec_literal, "k": K})
        rows = cur.fetchall()
    conn.rollback()  # SET LOCAL 효과 종료
    return [row[0] for row in rows]


def fetch_hnsw(
    conn: psycopg.Connection,
    vec_literal: str,
    ef_search: int,
    *,
    force_index: bool = False,
) -> tuple[list[str], float]:
    """ef_search 적용 후 HNSW Index Scan으로 top-K id 목록 + latency(s) 반환.

    force_index=True이면 enable_seqscan=off로 플래너가 인덱스를 선택하도록 강제한다.
    작은 N에서 인덱스가 자동 선택되지 않을 때 ef_search 영향을 측정하기 위해 사용.
    """
    collection_name = settings.PGVECTOR_COLLECTION_NAME
    sql = f"""
        SELECT e.id::text
        FROM langchain_pg_embedding e
        JOIN langchain_pg_collection c ON e.collection_id = c.uuid
        WHERE c.name = %(collection_name)s
        ORDER BY (e.embedding::vector({DIMS})) <=> %(vec)s::vector({DIMS})
        LIMIT %(k)s
    """
    with conn.cursor() as cur:
        cur.execute(f"SET LOCAL hnsw.ef_search = {ef_search}")
        cur.execute("SET LOCAL enable_indexscan = on")
        cur.execute("SET LOCAL enable_bitmapscan = on")
        if force_index:
            cur.execute("SET LOCAL enable_seqscan = off")
        start = time.perf_counter()
        cur.execute(sql, {"collection_name": collection_name, "vec": vec_literal, "k": K})
        rows = cur.fetchall()
        elapsed = time.perf_counter() - start
    conn.rollback()
    return [row[0] for row in rows], elapsed


def recall(seq_ids: list[str], hnsw_ids: list[str]) -> float:
    if not seq_ids:
        return 0.0
    return len(set(seq_ids) & set(hnsw_ids)) / len(set(seq_ids))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_v[int(k)]
    return sorted_v[f] + (sorted_v[c] - sorted_v[f]) * (k - f)


def count_rows(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = %(collection_name)s
            """,
            {"collection_name": settings.PGVECTOR_COLLECTION_NAME},
        )
        return cur.fetchone()[0]


def verify_index(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'langchain_pg_embedding' AND indexname = 'idx_embedding_hnsw'
            """
        )
        return cur.fetchone() is not None


def explain_plan(conn: psycopg.Connection, vec_literal: str, ef_search: int) -> str:
    """실제 쿼리의 실행 계획을 문자열로 반환."""
    collection_name = settings.PGVECTOR_COLLECTION_NAME
    sql = f"""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT e.id::text
        FROM langchain_pg_embedding e
        JOIN langchain_pg_collection c ON e.collection_id = c.uuid
        WHERE c.name = %(collection_name)s
        ORDER BY (e.embedding::vector({DIMS})) <=> %(vec)s::vector({DIMS})
        LIMIT %(k)s
    """
    with conn.cursor() as cur:
        cur.execute(f"SET LOCAL hnsw.ef_search = {ef_search}")
        cur.execute("SET LOCAL enable_indexscan = on")
        cur.execute("SET LOCAL enable_bitmapscan = on")
        cur.execute(sql, {"collection_name": collection_name, "vec": vec_literal, "k": K})
        rows = cur.fetchall()
    conn.rollback()
    return "\n".join(row[0] for row in rows)


def explain_plan_forced(conn: psycopg.Connection, vec_literal: str, ef_search: int) -> str:
    """enable_seqscan=off로 인덱스를 강제한 후의 실행 계획."""
    collection_name = settings.PGVECTOR_COLLECTION_NAME
    sql = f"""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT e.id::text
        FROM langchain_pg_embedding e
        JOIN langchain_pg_collection c ON e.collection_id = c.uuid
        WHERE c.name = %(collection_name)s
        ORDER BY (e.embedding::vector({DIMS})) <=> %(vec)s::vector({DIMS})
        LIMIT %(k)s
    """
    with conn.cursor() as cur:
        cur.execute(f"SET LOCAL hnsw.ef_search = {ef_search}")
        cur.execute("SET LOCAL enable_indexscan = on")
        cur.execute("SET LOCAL enable_bitmapscan = on")
        cur.execute("SET LOCAL enable_seqscan = off")
        cur.execute(sql, {"collection_name": collection_name, "vec": vec_literal, "k": K})
        rows = cur.fetchall()
    conn.rollback()
    return "\n".join(row[0] for row in rows)


def main():
    print("임베딩 모델 초기화 중...")
    embedder = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()

    conn_string = settings.sqlalchemy_database_url.replace("+psycopg", "")

    with psycopg.connect(conn_string) as conn:
        conn.autocommit = False

        if not verify_index(conn):
            print("[FATAL] idx_embedding_hnsw 인덱스가 존재하지 않습니다.")
            print("        PGVECTOR_HNSW_INDEX_ENABLED=True 후 서버를 한 번 실행해 인덱스를 생성하세요.")
            return

        n_rows = count_rows(conn)
        print(f"\n측정 대상: {n_rows} rows in collection '{settings.PGVECTOR_COLLECTION_NAME}'")
        print(f"K = {K}, repeats = {REPEATS}, ef_search ∈ {EF_SEARCH_VALUES}")

        # 첫 쿼리로 실행 계획 점검
        print("\n[실행 계획 점검 — ef_search=100, 첫 쿼리]")
        first_emb = embedder.embed_query(TEST_QUERIES[0])
        plan = explain_plan(conn, to_vec_literal(first_emb), 100)
        print(plan)
        # langchain_pg_embedding이 Seq Scan으로 도는지 확인 (다른 테이블의 Index Scan에 속지 않음)
        force_index = "Seq Scan on langchain_pg_embedding" in plan
        if force_index:
            print("\n[NOTICE] langchain_pg_embedding이 Seq Scan으로 도는 중 (작은 N).")
            print("  → enable_seqscan=off로 HNSW 인덱스를 강제하여 ef_search 영향만 측정합니다.")
            print("  → 절대 latency는 인공적이므로 recall 곡선 + 상대 latency만 신뢰하세요.")
            print("\n[강제 모드 EXPLAIN — ef_search=100]")
            forced_plan = explain_plan_forced(conn, to_vec_literal(first_emb), 100)
            print(forced_plan)

        # 쿼리별 임베딩 + ground truth 1회 추출
        print("\n임베딩 + Seq Scan ground truth 추출 중...")
        prepared = []
        for q in TEST_QUERIES:
            embedding = embedder.embed_query(q)
            vec_literal = to_vec_literal(embedding)
            seq_ids = fetch_seq_truth(conn, vec_literal)
            prepared.append((q, vec_literal, seq_ids))
            print(f"  - '{q[:30]}...' seq_top{K} = {len(seq_ids)} ids")

        # ef_search 루프
        print(f"\n{'='*78}")
        print(f"{'ef_search':>9} │ {'avg_ms':>8} │ {'p95_ms':>8} │ {'avg_recall':>10} │ per-query (recall, ms)")
        print(f"{'-'*78}")

        summary = []

        for ef in EF_SEARCH_VALUES:
            all_latencies_ms: list[float] = []
            recalls: list[float] = []
            per_query_brief: list[str] = []

            for q, vec_literal, seq_ids in prepared:
                # 워밍업 1회 (캐시 효과 안정화)
                fetch_hnsw(conn, vec_literal, ef, force_index=force_index)

                # 본 측정 REPEATS회
                q_latencies: list[float] = []
                last_ids: list[str] = []
                for _ in range(REPEATS):
                    ids, elapsed = fetch_hnsw(conn, vec_literal, ef, force_index=force_index)
                    q_latencies.append(elapsed * 1000)
                    last_ids = ids

                r = recall(seq_ids, last_ids)
                recalls.append(r)
                all_latencies_ms.extend(q_latencies)
                per_query_brief.append(f"({r:.2f}, {statistics.mean(q_latencies):.1f}ms)")

            avg_ms = statistics.mean(all_latencies_ms)
            p95_ms = percentile(all_latencies_ms, 0.95)
            avg_recall = statistics.mean(recalls)
            summary.append((ef, avg_ms, p95_ms, avg_recall))

            print(
                f"{ef:>9} │ {avg_ms:>8.2f} │ {p95_ms:>8.2f} │ {avg_recall:>10.3f} │ "
                + " ".join(per_query_brief)
            )

        print(f"{'='*78}")

        # 추정
        log_factor = math.log(120_000) / math.log(max(n_rows, 2))
        print(f"\n[120K rows 스케일 추정]")
        print(f"  현재 측정 데이터: {n_rows} rows → 프로덕션 추정: 120,000 rows")
        print(f"  HNSW search 복잡도 ≈ O(log N × ef_search)")
        print(f"  log({120_000}) / log({n_rows}) = {log_factor:.2f}")
        print(f"  → 동일 ef_search에서 latency 약 {log_factor:.2f}배 (실측치는 더 클 수 있음, 1.4~1.7 범위 보수적 추정)")
        print(f"\n[권장 결정 기준]")
        print(f"  - ef_search ≥ K (= {K}) 미충족 구간은 recall 비정상")
        print(f"  - recall이 0.99+ 평탄화되는 가장 작은 ef_search 선택")
        print(f"  - 해당 latency × 1.4~1.7 ≈ 프로덕션 예상 latency")


if __name__ == "__main__":
    main()
