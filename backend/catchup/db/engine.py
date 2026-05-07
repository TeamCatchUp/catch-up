import logging
import re
import threading

import structlog
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings

logger = logging.getLogger(__name__)
_explain_logger = structlog.get_logger(__name__)
_explain_active = threading.local()

_VECTOR_LITERAL_RE = re.compile(r"'\[[\d\s.,\-e]+\]'::vector")
_EXECUTION_TIME_RE = re.compile(r"^Execution Time:\s*([\d.]+)", re.MULTILINE)
_PLANNING_TIME_RE = re.compile(r"^Planning Time:\s*([\d.]+)", re.MULTILINE)
_ACTUAL_ROWS_RE = re.compile(r"actual time=[\d.]+\.\.[\d.]+ rows=(\d+)")


def parse_plan(plan_lines: list[str]) -> dict:
    """EXPLAIN ANALYZE 텍스트에서 핵심 지표를 추출한다."""
    full = "\n".join(plan_lines)
    full = _VECTOR_LITERAL_RE.sub("'[...vector...]'::vector", full)
    cleaned = [_VECTOR_LITERAL_RE.sub("'[...vector...]'::vector", l) for l in plan_lines]

    metrics: dict = {"plan": cleaned}

    if m := _EXECUTION_TIME_RE.search(full):
        metrics["execution_ms"] = float(m.group(1))
    if m := _PLANNING_TIME_RE.search(full):
        metrics["planning_ms"] = float(m.group(1))

    if "Seq Scan" in full:
        metrics["scan_type"] = "seq_scan"
    elif "Index Scan" in full:
        metrics["scan_type"] = "index_scan"
    elif "Bitmap" in full:
        metrics["scan_type"] = "bitmap_scan"

    if rows := _ACTUAL_ROWS_RE.findall(full):
        metrics["actual_rows"] = int(rows[0])

    return metrics

engine = create_engine(
    settings.sqlalchemy_database_url,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
)


@event.listens_for(engine, "connect")
def set_session_params(dbapi_connection, connection_record):
    """
    pg_bigm 유사도 임계값과 HNSW ef_search를 커넥션 수립 시점에 설정한다.
    매 쿼리마다 SET LOCAL을 실행하는 오버헤드를 방지하고,
    set_config(...)를 단일 SELECT로 묶어 RTT를 1회로 유지한다.

    hnsw.ef_search=200: hybrid_search가 k=100을 요청하므로 ef_search >= k 보장 필요.
    측정상 ef_search=40에서 K=100 recall이 0.4로 깨지고, 200에서 0.99+로 수렴.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(
            "SELECT set_config('pg_bigm.similarity_limit', '0.02', false), "
            "       set_config('hnsw.ef_search', '200', false)"
        )
    except Exception as e:
        logger.warning(f"Failed to set session params: {e}")
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine)


@event.listens_for(engine, "before_cursor_execute", retval=True)
def explain_vector_queries(conn, cursor, statement, parameters, context, executemany):
    """
    ENABLE_QUERY_EXPLAIN=true일 때 pgvector 쿼리(<=>) 실행 전 EXPLAIN (ANALYZE, BUFFERS)를 구동하고
    결과를 서버 로그로 출력한다. before_cursor_execute에서 동일 cursor를 재사용하므로
    thread-local 가드로 재귀 호출을 방지한다.
    """
    if (
        settings.ENABLE_QUERY_EXPLAIN
        and not getattr(_explain_active, "active", False)
        and not executemany
        and "<=>" in statement
    ):
        _explain_active.active = True
        try:
            cursor.execute(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + statement,
                parameters,
            )
            metrics = parse_plan([row[0] for row in cursor.fetchall()])
            _explain_logger.info("vector_query_plan", **metrics)
        except Exception as e:
            _explain_logger.warning("vector_query_plan_failed", error=str(e))
        finally:
            _explain_active.active = False
    return statement, parameters
