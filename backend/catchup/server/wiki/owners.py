"""문서에 붙는 사람을 이름·사진과 함께 응답 모양으로 조립한다.

담당자와 최종 편집자를 같은 모양으로 내보낸다. wiki 라우터와
knowledge_review 라우터가 같은 표시를 쓰는데, 조립을 라우터마다 따로 두면
한쪽만 필드를 늘렸을 때 같은 사람이 화면에 따로 보인다.
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


def users_by_id(
    db: Session, user_ids: Sequence[int | None]
) -> dict[int, OwnerResponse]:
    """사용자 id마다 사람 응답을 만들어 묶는다.

    사용자를 한 번에 읽고 나눈다. 행마다 따로 읽으면 목록 한 쪽에 질의가
    줄 수만큼 늘어난다. None과 중복은 걸러서 넘긴다.

    사용자 행이 사라진 id는 결과에 키가 없다. 부르는 쪽은 그 경우 사람을
    비운다.
    """
    wanted = sorted({user_id for user_id in user_ids if user_id is not None})
    if not wanted:
        return {}

    users = wiki_queries.list_users_for_display(db, user_ids=wanted)
    return {
        user_id: OwnerResponse(
            user_id=row.user_id,
            display_name=row.display_name,
            profile_image_url=row.profile_image_url,
        )
        for user_id, row in users.items()
    }


# 승인 기록에 남는 승인자 문자열은 정상 승인 경로에서 "user:" 뒤에 사용자
# id를 붙인 모양이다. 디버그 경로는 다른 모양으로 남기므로, 접두가 다르거나
# 뒤가 정수가 아니면 사람으로 옮기지 않는다.
_REVIEWER_USER_PREFIX = "user:"


def reviewer_user_id(reviewer: str | None) -> int | None:
    """승인자 문자열에서 사용자 id를 읽는다. 사람으로 옮길 수 없으면 None이다."""
    if reviewer is None or not reviewer.startswith(_REVIEWER_USER_PREFIX):
        return None

    tail = reviewer[len(_REVIEWER_USER_PREFIX) :]
    if not tail.isdigit():
        return None

    return int(tail)


def editors_by_reviewer(
    db: Session, reviewers: Sequence[str | None]
) -> dict[str, OwnerResponse]:
    """승인자 문자열마다 사람 응답을 만들어 묶는다.

    사용자를 한 번에 읽고 나눈다. 문서마다 따로 읽으면 목록 한 쪽에 질의가
    줄 수만큼 늘어난다.

    사람으로 옮길 수 없는 승인자와 사용자 행이 사라진 승인자는 결과에 키가
    없다. 부르는 쪽은 그 경우 편집자를 비운다.
    """
    wanted = {
        reviewer: user_id
        for reviewer in reviewers
        if reviewer is not None
        and (user_id := reviewer_user_id(reviewer)) is not None
    }
    if not wanted:
        return {}

    users = wiki_queries.list_users_for_display(
        db, user_ids=sorted(set(wanted.values()))
    )
    return {
        reviewer: OwnerResponse(
            user_id=users[user_id].user_id,
            display_name=users[user_id].display_name,
            profile_image_url=users[user_id].profile_image_url,
        )
        for reviewer, user_id in wanted.items()
        if user_id in users
    }
