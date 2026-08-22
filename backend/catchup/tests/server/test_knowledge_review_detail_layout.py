"""검수 상세 응답에 실리는 읽기 레이아웃을 실 PostgreSQL로 확인한다.

레이아웃은 읽기 표현일 뿐이라 저장된 블록 배열과 그 순서를 바꾸지 않는다.
그래서 여기서 보는 것은 두 가지다. layout의 block_index가 blocks의 자리와
정확히 같은가, 그리고 발행판 블록에도 같은 규칙이 적용되는가다. 자리가
어긋나면 검토자가 고른 블록과 저장된 블록이 달라진다.

픽스처는 기존 검수 API 테스트의 것을 그대로 가져다 쓴다. 같은 실 DB
연결·앱·사용자 준비를 두 벌로 두면 한쪽만 고쳐질 때 둘이 갈린다.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeNode
from catchup.db.models import User
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.server.knowledge_review.dependencies import get_review_uow_factory
from catchup.tests.server.test_knowledge_review_api import AT
from catchup.tests.server.test_knowledge_review_api import _fake_factory
from catchup.tests.server.test_knowledge_review_api import _FakeArtifacts
from catchup.tests.server.test_knowledge_review_api import _seed_revision
from catchup.tests.server.test_knowledge_review_api import app  # noqa: F401
from catchup.tests.server.test_knowledge_review_api import as_user  # noqa: F401
from catchup.tests.server.test_knowledge_review_api import client  # noqa: F401
from catchup.tests.server.test_knowledge_review_api import connection  # noqa: F401
from catchup.tests.server.test_knowledge_review_api import db  # noqa: F401
from catchup.tests.server.test_knowledge_review_api import engine  # noqa: F401
from catchup.tests.server.test_knowledge_review_api import reviewer  # noqa: F401
from catchup.tests.server.test_knowledge_review_api import session_factory  # noqa: F401
from catchup.tests.server.test_knowledge_review_api import workspace_ids  # noqa: F401


def _make_voc_artifact(db: Session, *, workspace_id: int) -> uuid.UUID:
    """읽기 레이아웃이 있는 kind의 문서 한 편을 만든다."""
    node_id = uuid.uuid4()
    db.add(
        KnowledgeNode(
            id=node_id,
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="feature_request",
            canonical_key=f"test:layout:{uuid.uuid4().hex}",
            display_name="엑셀 내려받기",
        )
    )
    db.flush()
    artifact_id = uuid.uuid4()
    db.add(
        KnowledgeArtifact(
            id=artifact_id,
            workspace_id=workspace_id,
            kind="feature_request_status",
            subject_node_id=node_id,
            title="요청 현황: 엑셀 내려받기",
        )
    )
    db.flush()
    return artifact_id


def _section(heading: str, body: str) -> ArtifactBlock:
    """절 블록 하나를 만든다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading=heading,
        body=body,
        claim_ids=(uuid.uuid4(),),
        proposal_ids=(),
        ontology_version="v1",
    )


def _layout_proposal(
    *, proposal_id: uuid.UUID, artifact_id: uuid.UUID
) -> StoredArtifactProposal:
    """머리말 블록 셋과 양식이 이름을 댄 절 블록들을 담은 변경안을 만든다.

    저장 순서를 양식 순서와 어긋나게 둔다. layout이 저장 순서가 아니라
    양식 순서를 따르는지 보려면 두 순서가 달라야 한다.
    """
    return StoredArtifactProposal(
        id=proposal_id,
        artifact_id=artifact_id,
        subject_node_id=uuid.uuid4(),
        title="요청 현황: 엑셀 내려받기",
        status="pending",
        blocks=(
            *(
                ArtifactBlock(
                    block_kind=BLOCK_KIND_SUMMARY,
                    heading=section_key,
                    body="claim 2건",
                    claim_ids=(uuid.uuid4(),),
                    proposal_ids=(),
                    ontology_version="v1",
                )
                for section_key in (
                    "one_line_summary",
                    "desired_outcome",
                    "background",
                )
            ),
            _section("last_reported_at", "2026-08-15에 다시 접수됐다"),
            _section("request_status", "상태는 검토중이다"),
        ),
        content_hash="hash",
        base_revision_id=None,
        rejection_reason=None,
        origin="compiled",
        created_at=AT,
    )


@pytest.fixture
def artifact_id(db: Session, workspace_ids: tuple[int, int]) -> uuid.UUID:
    """레이아웃이 있는 kind의 문서 하나를 세운다."""
    workspace_id, _ = workspace_ids
    return _make_voc_artifact(db, workspace_id=workspace_id)


def test_detail_layout_indexes_match_blocks_and_changes(
    app: FastAPI,
    client: TestClient,
    db: Session,
    reviewer: User,
    workspace_ids: tuple[int, int],
    artifact_id: uuid.UUID,
) -> None:
    """layout의 block 항목이 blocks의 모든 자리를 그대로 가리킨다."""
    workspace_id, _ = workspace_ids
    _seed_revision(
        db,
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        blocks=(_section("request_status", "상태는 수집됨이다"),),
    )
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_layout_proposal(
                proposal_id=proposal_id, artifact_id=artifact_id
            )
        )
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    data = response.json()
    indexes = {
        item["block_index"]
        for item in data["layout"]
        if item["item_kind"] == "block"
    }
    assert indexes == set(range(len(data["blocks"])))
    for change in data["block_changes"]:
        if change["block_index"] is not None:
            assert change["block_index"] in indexes
    assert len(data["base_layout"]) >= 1


def test_detail_layout_follows_catalog_order(
    app: FastAPI,
    client: TestClient,
    db: Session,
    reviewer: User,
    workspace_ids: tuple[int, int],
    artifact_id: uuid.UUID,
) -> None:
    """layout은 저장 순서가 아니라 문서 종류의 양식 순서를 따른다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_layout_proposal(
                proposal_id=proposal_id, artifact_id=artifact_id
            )
        )
    )

    data = client.get(
        f"/api/v1/knowledge-review/queue/{proposal_id}"
    ).json()

    assert data["layout"][0]["block_index"] == 0
    headings = [item["heading"] for item in data["layout"]]
    assert headings.index("요청 상태") < headings.index("최근 보고")


def test_detail_without_revision_has_empty_base_layout(
    app: FastAPI,
    client: TestClient,
    db: Session,
    reviewer: User,
    workspace_ids: tuple[int, int],
    artifact_id: uuid.UUID,
) -> None:
    """발행판이 없으면 base_layout도 빈 목록이다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_layout_proposal(
                proposal_id=proposal_id, artifact_id=artifact_id
            )
        )
    )

    data = client.get(
        f"/api/v1/knowledge-review/queue/{proposal_id}"
    ).json()

    assert data["base_blocks"] == []
    assert data["base_layout"] == []


def test_detail_layout_labels_the_summary_sections(
    app: FastAPI,
    client: TestClient,
    db: Session,
    reviewer: User,
    workspace_ids: tuple[int, int],
    artifact_id: uuid.UUID,
) -> None:
    """머리말 세 블록이 양식 제목을 달고 맨 앞 세 항목으로 나온다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_layout_proposal(
                proposal_id=proposal_id, artifact_id=artifact_id
            )
        )
    )

    data = client.get(
        f"/api/v1/knowledge-review/queue/{proposal_id}"
    ).json()

    assert [
        (item["heading"], item["block_index"])
        for item in data["layout"][:3]
    ] == [("한 줄 요약", 0), ("원하는 결과", 1), ("요청 배경", 2)]


def test_detail_block_response_has_no_summary_sections_field(
    app: FastAPI,
    client: TestClient,
    db: Session,
    reviewer: User,
    workspace_ids: tuple[int, int],
    artifact_id: uuid.UUID,
) -> None:
    """블록이 곧 섹션이므로 파생 필드를 따로 싣지 않는다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_layout_proposal(
                proposal_id=proposal_id, artifact_id=artifact_id
            )
        )
    )

    data = client.get(
        f"/api/v1/knowledge-review/queue/{proposal_id}"
    ).json()

    assert all("summary_sections" not in block for block in data["blocks"])
