"""
HNSW 인덱스 A/B 테스트

Seq Scan(인덱스 없음) vs HNSW Index Scan을 같은 DB에서 비교한다.
- 쿼리 실행 시간 (latency)
- 결과 일치율 (recall): Seq Scan 결과 대비 HNSW 결과의 overlap

실행 방법:
    cd backend
    python -m catchup.evaluation.eval_vector_index

환경 변수 (.env):
    DATABASE_URL, AWS_REGION, PGVECTOR_COLLECTION_NAME 등 서버와 동일하게 설정
"""

import os
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

# 테스트 쿼리 목록 — 실제 서비스에서 자주 쓰이는 질문으로 교체
TEST_QUERIES = [
    "어제 오늘까지 해서 Slack Bot 구현된 내용 보여줘",
    "가장 최근 PR 내용 찾아줘",
    "최근에 감사로그 컬럼 정리된 문서 어디있더라?",
    "에이전트 스튜디오 관련 기획 문서 찾아줘",
    "디자인 qa 진행상황을 알려줘",
]

K = 20  # 비교할 상위 결과 수


def embed_query(embedder, query: str) -> list[float]:
    return embedder.embed_query(query)


def run_similarity_search(
    conn: psycopg.Connection,
    embedding: list[float],
    k: int,
    *,
    use_index: bool,
) -> tuple[list[str], float]:
    """
    벡터 유사도 검색을 실행하고 (결과 id 목록, 실행시간(s))을 반환한다.
    use_index=False 이면 세션 레벨로 인덱스 스캔을 비활성화하여 Seq Scan을 강제한다.
    """
    vec_literal = f"[{','.join(str(v) for v in embedding)}]"
    collection_name = settings.PGVECTOR_COLLECTION_NAME

    toggle_sql = (
        "SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off;"
        if not use_index
        else
        "SET LOCAL enable_indexscan = on; SET LOCAL enable_bitmapscan = on;"
    )

    search_sql = f"""
        SELECT e.id::text
        FROM langchain_pg_embedding e
        JOIN langchain_pg_collection c ON e.collection_id = c.uuid
        WHERE c.name = %(collection_name)s
        ORDER BY (e.embedding::vector({DIMS})) <=> %(vec)s::vector({DIMS})
        LIMIT %(k)s
    """

    with conn.cursor() as cur:
        cur.execute(toggle_sql)
        start = time.perf_counter()
        cur.execute(search_sql, {"collection_name": collection_name, "vec": vec_literal, "k": k})
        rows = cur.fetchall()
        elapsed = time.perf_counter() - start

    ids = [row[0] for row in rows]
    return ids, elapsed


def recall(seq_ids: list[str], hnsw_ids: list[str]) -> float:
    if not seq_ids:
        return 0.0
    return len(set(seq_ids) & set(hnsw_ids)) / len(set(seq_ids))


def main():
    print("임베딩 모델 초기화 중...")
    embedder = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()

    conn_string = settings.sqlalchemy_database_url.replace("+psycopg", "")

    print(f"\n{'='*60}")
    print(f"  HNSW Index A/B Test  (K={K}, dims={DIMS})")
    print(f"{'='*60}")
    print(f"{'Query':<30} {'SeqScan':>10} {'HNSW':>10} {'Speedup':>10} {'Recall':>8}")
    print(f"{'-'*60}")

    total_seq, total_hnsw, total_recall = 0.0, 0.0, 0.0

    with psycopg.connect(conn_string) as conn:
        conn.autocommit = False  # SET LOCAL이 트랜잭션 범위에서 동작하도록

        for query in TEST_QUERIES:
            embedding = embed_query(embedder, query)

            seq_ids, seq_time = run_similarity_search(conn, embedding, K, use_index=False)
            hnsw_ids, hnsw_time = run_similarity_search(conn, embedding, K, use_index=True)

            r = recall(seq_ids, hnsw_ids)
            speedup = seq_time / hnsw_time if hnsw_time > 0 else float("inf")

            label = query[:28] + ".." if len(query) > 30 else query
            print(f"{label:<30} {seq_time:>9.3f}s {hnsw_time:>9.3f}s {speedup:>9.1f}x {r:>7.1%}")

            total_seq += seq_time
            total_hnsw += hnsw_time
            total_recall += r

    n = len(TEST_QUERIES)
    avg_speedup = (total_seq / n) / (total_hnsw / n) if total_hnsw > 0 else float("inf")
    print(f"{'-'*60}")
    print(f"{'평균':<30} {total_seq/n:>9.3f}s {total_hnsw/n:>9.3f}s {avg_speedup:>9.1f}x {total_recall/n:>7.1%}")
    print(f"{'='*60}")

    print("\n[Recall 해석]")
    print("  100%: HNSW 결과가 Seq Scan과 완전히 동일 (approximate 오차 없음)")
    print("   95%+: 실용적 수준 (ANN 특성상 정상)")
    print("  <90%: ef_search 값 상향 검토 필요 (기본 40 → 100)")


if __name__ == "__main__":
    main()
