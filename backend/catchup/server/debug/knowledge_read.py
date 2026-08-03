"""특정 시점에 참이었던 claim을 읽는 debug 전용 엔드포인트다.

as-of 조회를 CLI 없이 눈으로 확인할 창구다. 읽기만 하므로 commit이
없고, 결정도 내리지 않는다. 매칭 규칙과 구간 판정은 전부 서비스와
reader가 갖고 있고 이 라우터는 쿼리 파라미터를 파싱해 넘기고 결과를
JSON으로 옮기는 껍데기다.

인증은 붙이지 않는다. `DEBUG_API_ENABLED`이고 ENV가 development일 때만
등록되는 개발 도구이기 때문이다.

valid_from과 valid_to는 null을 그대로 내보낸다. "언제부터인지 모른다"와
"아직 안 끝났다"는 소비자가 구분해야 할 정보지, 임의의 시각으로 메워
없앨 정보가 아니다.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

import structlog
from fastapi import APIRouter
from fastapi import HTTPException

from catchup.configs.config import Environment
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_as_of,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


def _guard() -> None:
    """개발 환경 밖에서는 어떤 요청도 받지 않는다."""
    if settings.ENV is not Environment.development:
        raise HTTPException(
            status_code=403,
            detail="development 환경에서만 쓸 수 있다.",
        )


def _parse_at(raw: str | None) -> datetime | None:
    """`at` 쿼리 파라미터를 timezone 있는 시각으로 바꾼다.

    timezone이 없으면 UTC로 본다. 서비스는 naive를 거부하므로 여기서
    한 번 정해 두지 않으면 사용자가 매번 오프셋을 적어야 한다.
    """
    if raw is None:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=f"at은 ISO-8601 시각이어야 한다: {raw}",
        ) from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


@router.get("/knowledge-read/claims")
def read_claims_as_of(
    subject: str,
    at: str | None = None,
    predicate: str | None = None,
    workspace_id: int = 1,
) -> dict[str, Any]:
    """subject가 at 시점에 갖고 있던 accepted claim을 돌려준다."""
    _guard()
    result = query_claims_as_of(
        workspace_id=workspace_id,
        subject=subject,
        at=_parse_at(at),
        predicate=predicate,
        uow=KnowledgeMaintenanceUnitOfWork(SessionLocal, workspace_id=workspace_id),
    )
    return {
        "as_of": result.as_of.isoformat(),
        "subject": (
            None
            if result.subject is None
            else {
                "node_id": str(result.subject.node_id),
                "entity_type": result.subject.entity_type,
                "display_name": result.subject.display_name,
                "matched_by": result.subject.matched_by,
            }
        ),
        "claims": [
            {
                "claim_id": str(claim.claim_id),
                "predicate": claim.predicate,
                "value_type": claim.value_type,
                "value": claim.value,
                "statement": claim.statement,
                "valid_from": (
                    None if claim.valid_from is None else claim.valid_from.isoformat()
                ),
                "valid_to": (
                    None if claim.valid_to is None else claim.valid_to.isoformat()
                ),
            }
            for claim in result.claims
        ],
    }
