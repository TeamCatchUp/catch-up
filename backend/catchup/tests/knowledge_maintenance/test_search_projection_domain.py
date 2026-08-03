"""published revision 블록을 검색 문서로 옮기는 매핑을 검증한다."""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.search_projection import (
    project_revision_blocks,
)

ARTIFACT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
REVISION_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def _block_claim_ids() -> tuple[uuid.UUID, ...]:
    """블록이 근거로 삼는 claim id들을 돌려준다."""
    return (uuid.UUID("33333333-3333-4333-8333-333333333333"),)


def _block(*, heading: str, body: str) -> ArtifactBlock:
    """기본값으로 claim_section 블록 하나를 조립한다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading=heading,
        body=body,
        claim_ids=_block_claim_ids(),
        proposal_ids=(),
        ontology_version="v1",
    )


def test_projects_block_to_document() -> None:
    docs = project_revision_blocks(
        workspace_id=1,
        artifact_id=ARTIFACT_ID,
        revision_id=REVISION_ID,
        revision_number=3,
        title="캐치업 오픈 API",
        blocks=[_block(heading="rate_limit_per_minute", body="60 (관찰)")],
        created_at=NOW,
    )
    doc = docs[0]
    assert doc.document_id == (
        f"llm_wiki:artifact_revision:{ARTIFACT_ID}"
        f":block:claim_section:rate_limit_per_minute"
    )
    assert doc.content == "캐치업 오픈 API — rate_limit_per_minute: 60 (관찰)"
    assert doc.metadata["source"] == "llm_wiki"
    assert doc.metadata["entity_type"] == "artifact_revision"
    assert doc.metadata["scope_id"] == 1
    assert doc.metadata["artifact_id"] == str(ARTIFACT_ID)
    assert doc.metadata["revision_id"] == str(REVISION_ID)
    assert doc.metadata["revision_number"] == 3
    assert doc.metadata["title"] == "캐치업 오픈 API"
    assert doc.metadata["heading"] == "rate_limit_per_minute"
    assert doc.metadata["claim_ids"] == [str(c) for c in _block_claim_ids()]
    assert "contextual_content" in doc.metadata
    assert doc.metadata["created_at"] == NOW.isoformat()


def test_duplicate_anchor_gets_index_suffix() -> None:
    blocks = [
        _block(heading="status", body="a"),
        _block(heading="status", body="b"),
    ]
    docs = project_revision_blocks(
        workspace_id=1,
        artifact_id=ARTIFACT_ID,
        revision_id=REVISION_ID,
        revision_number=3,
        title="캐치업 오픈 API",
        blocks=blocks,
        created_at=NOW,
    )
    assert docs[0].document_id.endswith(":status")
    assert docs[1].document_id.endswith(":status:2")


def test_empty_blocks_project_nothing() -> None:
    assert (
        project_revision_blocks(
            workspace_id=1,
            artifact_id=ARTIFACT_ID,
            revision_id=REVISION_ID,
            revision_number=3,
            title="캐치업 오픈 API",
            blocks=[],
            created_at=NOW,
        )
        == ()
    )
