"""knowledge_maintenance 평가 데이터를 비우는 debug 전용 엔드포인트다.

파이프라인을 손으로 돌리는 개발 사이클에서 수집 → 추출 → 확인 → 초기화가
잦다. 매번 psql로 TRUNCATE를 붙여 넣지 않도록 초기화만 하는 엔드포인트를
둔다.

`DEBUG_API_ENABLED`일 때만 등록되며, 그 위에 ENV가 development가 아니면
거부한다. 지우는 것은 로컬 평가 데이터뿐이고 payload 파일에서 언제든
다시 만들 수 있다.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from catchup.configs.config import Environment
from catchup.configs.config import settings
from catchup.db.dependencies import get_db

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])

# TRUNCATE 대상. knowledge_maintenance 파이프라인이 쓰는 테이블 전부이며,
# 이 목록 밖의 테이블은 건드리지 않는다.
KNOWLEDGE_MAINTENANCE_TABLES = (
    "source_versions",
    "observations",
    "knowledge_nodes",
    "knowledge_pipeline_outbox",
    "knowledge_ontology_snapshots",
    "knowledge_extraction_runs",
    "knowledge_entity_candidates",
    "knowledge_claim_candidates",
    "knowledge_relation_assertion_candidates",
    "knowledge_candidate_evidence_links",
)


@router.post("/knowledge-maintenance/reset")
def reset_knowledge_maintenance(db: Session = Depends(get_db)) -> dict:
    """knowledge_maintenance 테이블을 전부 비우고 지운 행 수를 알려준다."""
    if settings.ENV is not Environment.development:
        raise HTTPException(
            status_code=403,
            detail="development 환경에서만 초기화할 수 있다.",
        )

    deleted: dict[str, int] = {}
    for table in KNOWLEDGE_MAINTENANCE_TABLES:
        deleted[table] = db.execute(
            text(f"SELECT count(*) FROM {table}")  # noqa: S608 — 고정 목록
        ).scalar_one()

    tables = ", ".join(KNOWLEDGE_MAINTENANCE_TABLES)
    db.execute(text(f"TRUNCATE {tables} CASCADE"))
    db.commit()

    logger.warning("knowledge_maintenance_reset", deleted=deleted)
    return {"deleted": deleted}
