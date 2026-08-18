"""문서 담당자를 이름·사진과 함께 응답 모양으로 조립한다.

wiki 라우터와 knowledge_review 라우터가 같은 담당자 표시를 쓴다. 조립을
라우터마다 따로 두면 한쪽만 필드를 늘렸을 때 같은 담당자가 화면에 따로
보이므로, 조립 지점을 하나로 둔다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from catchup.db import wiki as wiki_queries
from catchup.server.wiki.schemas import OwnerResponse


def owners_by_artifact(
    db: Session, artifact_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[OwnerResponse]]:
    """문서 id마다 담당자 응답 목록을 만든다.

    담당자가 없는 문서도 빈 목록으로 키를 채운다. 질의는 담당자가 없는
    문서를 결과에서 빼는데, 부르는 쪽이 그 차이를 매번 다루면 KeyError가
    날 자리가 라우터마다 생긴다.
    """
    rows = wiki_queries.list_owners_by_artifact(db, artifact_ids=artifact_ids)
    return {
        artifact_id: [
            OwnerResponse(
                user_id=row.user_id,
                display_name=row.display_name,
                profile_image_url=row.profile_image_url,
            )
            for row in rows.get(artifact_id, [])
        ]
        for artifact_id in artifact_ids
    }
