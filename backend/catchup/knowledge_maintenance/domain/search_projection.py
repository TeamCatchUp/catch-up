"""published revision 블록을 검색 문서로 옮기는 순수 매핑이다.

검색 인덱스는 원장에서 rebuild 가능한 projection이며 canonical이
아니다. 임베딩·저장은 adapter의 몫이고, 여기서는 어떤 블록이 어떤
문서가 되는지만 정한다 — 결정론이어야 재투영이 항상 같은 결과를
낸다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock

SOURCE = "llm_wiki"
ENTITY_TYPE = "artifact_revision"


@dataclass(frozen=True, slots=True)
class ProjectionDocument:
    """검색 인덱스에 실을 문서 하나를 표현한다.

    Attributes:
        document_id: 재투영해도 같은 블록이면 같은 값이 되는 안정
            식별자다. upsert와 중복 방지의 근거가 된다.
        content: 임베딩과 키워드 검색의 대상 본문이다.
        metadata: cmetadata로 저장될 부가 정보다.
    """

    document_id: str
    content: str
    metadata: dict[str, object]


def project_revision_blocks(
    *,
    workspace_id: int,
    artifact_id: uuid.UUID,
    revision_id: uuid.UUID,
    revision_number: int,
    title: str,
    blocks: Sequence[ArtifactBlock],
    created_at: datetime,
) -> tuple[ProjectionDocument, ...]:
    """current revision의 블록들을 검색 문서로 바꾼다.

    블록 하나가 문서 하나다. 앵커는 block_kind와 heading으로 만들고,
    같은 앵커가 겹치면 순번을 붙인다 — ArtifactBlock에 고유 id가
    없기 때문이다.
    """
    documents: list[ProjectionDocument] = []
    seen: dict[str, int] = {}
    for block in blocks:
        anchor = f"{block.block_kind}:{block.heading}"
        count = seen.get(anchor, 0) + 1
        seen[anchor] = count
        if count > 1:
            anchor = f"{anchor}:{count}"
        content = f"{title} — {block.heading}: {block.body}"
        documents.append(
            ProjectionDocument(
                document_id=(
                    f"{SOURCE}:{ENTITY_TYPE}:{artifact_id}:block:{anchor}"
                ),
                content=content,
                metadata={
                    "source": SOURCE,
                    "entity_type": ENTITY_TYPE,
                    "scope_id": workspace_id,
                    "artifact_id": str(artifact_id),
                    "revision_id": str(revision_id),
                    "revision_number": revision_number,
                    "title": title,
                    "heading": block.heading,
                    "claim_ids": [
                        str(claim_id) for claim_id in block.claim_ids
                    ],
                    "contextual_content": content,
                    "created_at": created_at.isoformat(),
                    "updated_at": created_at.isoformat(),
                },
            )
        )
    return tuple(documents)
