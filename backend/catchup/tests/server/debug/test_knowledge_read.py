"""debug 지식 조회 라우터가 결과를 JSON으로 옮기는지 확인한다.

서비스는 이미 별도로 검증하므로 여기서는 서비스를 대역으로 바꾸고
응답 모양만 본다. 라우터가 껍데기라는 것이 검증 대상이다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timezone
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.configs.config import Environment
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.services.query_knowledge_as_of import AsOfQueryResult
from catchup.knowledge_maintenance.services.query_knowledge_as_of import MatchedSubject
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    SubjectCandidate,
)
from catchup.server.debug.knowledge_read import router

AT = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def _development_env():
    """라우터의 개발 환경 가드를 통과시킨다."""
    with patch("catchup.server.debug.knowledge_read.settings") as fake_settings:
        fake_settings.ENV = Environment.development
        yield


@pytest.fixture(autouse=True)
def _no_database():
    """라우터가 만드는 unit of work가 DB를 건드리지 않게 한다."""
    with (
        patch(
            "catchup.server.debug.knowledge_read.KnowledgeMaintenanceUnitOfWork",
            MagicMock(),
        ),
        patch("catchup.server.debug.knowledge_read.SessionLocal", MagicMock()),
    ):
        yield


def _patch_service(result: AsOfQueryResult):
    return patch(
        "catchup.server.debug.knowledge_read.query_claims_as_of",
        return_value=result,
    )


def test_miss_response_exposes_similar_candidates() -> None:
    """정확 일치가 없으면 유사 후보가 응답에 실린다."""
    candidate = SubjectCandidate(
        node_id=uuid.uuid4(),
        display_name="캐치업 오픈 API 결제",
        entity_type="feature",
        score=0.42,
    )
    result = AsOfQueryResult(
        subject=None,
        as_of=AT,
        claims=(),
        similar_candidates=(candidate,),
    )

    with _patch_service(result):
        response = client.get(
            "/api/v1/debug/knowledge-read/claims",
            params={"subject": "캐치업 오픈 API"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["subject"] is None
    assert data["claims"] == []
    assert data["similar_candidates"] == [
        {
            "node_id": str(candidate.node_id),
            "display_name": "캐치업 오픈 API 결제",
            "entity_type": "feature",
            "score": 0.42,
        }
    ]


def test_exact_match_response_has_empty_candidates() -> None:
    """정확 일치면 후보 자리는 빈 배열로 남는다."""
    node_id = uuid.uuid4()
    claim = AsOfClaim(
        claim_id=uuid.uuid4(),
        predicate="rate_limit",
        value_type="number",
        value=60,
        statement="rate_limit은 60이다",
        valid_from=None,
        valid_to=None,
    )
    result = AsOfQueryResult(
        subject=MatchedSubject(
            node_id=node_id,
            entity_type="feature",
            display_name="오픈 API",
            matched_by="canonical_key",
        ),
        as_of=AT,
        claims=(claim,),
    )

    with _patch_service(result):
        response = client.get(
            "/api/v1/debug/knowledge-read/claims",
            params={"subject": "feature:오픈 api"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["similar_candidates"] == []
    assert data["subject"]["node_id"] == str(node_id)
    assert data["subject"]["matched_by"] == "canonical_key"
    assert data["as_of"] == AT.isoformat()
    assert [item["claim_id"] for item in data["claims"]] == [str(claim.claim_id)]


def test_candidate_without_display_name_keeps_nulls() -> None:
    """이름이나 종류가 비어도 임의 값으로 메우지 않는다."""
    candidate = SubjectCandidate(
        node_id=uuid.uuid4(),
        display_name=None,
        entity_type=None,
        score=0.15,
    )
    result = AsOfQueryResult(
        subject=None,
        as_of=AT,
        claims=(),
        similar_candidates=(candidate,),
    )

    with _patch_service(result):
        response = client.get(
            "/api/v1/debug/knowledge-read/claims",
            params={"subject": "없는 이름"},
        )

    assert response.status_code == 200
    item = response.json()["similar_candidates"][0]
    assert item["display_name"] is None
    assert item["entity_type"] is None
