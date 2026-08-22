"""위키 역할(관리자·담당자)의 적재와 판정을 담당한다.

검수 권한 판정을 담당한다: 담당자는 자기 문서만, 담당자가 없는 문서는
workspace 구성원 누구나다. 담당자 지정은 규칙이 달라, 관리자가 모든 문서에
서고 미분류(channel_id 없음) 문서의 관리자는 전역 ADMIN이다. 판정 함수는
순수 함수로 두어 fake 없이 단위 테스트한다.

적재는 db 세션을 받는 모듈 함수 하나(`load_wiki_roles`)로, 쿼리 자체는
`catchup.db.wiki`에 두고 여기서는 결과를 스냅샷으로 조립하기만 한다.
UnitOfWork의 내부 세션을 꺼내 쓰면 저장소 경계를 넘게 되므로, 역할과 대상
판정에 필요한 조회는 라우터가 가진 db 의존성으로만 나간다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from catchup.db import wiki as wiki_queries
from catchup.db.models import UserRole


@dataclass(frozen=True, slots=True)
class WikiRoleContext:
    """사용자 한 명의 위키 역할 스냅샷을 담는다."""

    is_global_admin: bool
    admin_channel_ids: frozenset[uuid.UUID]
    owned_artifact_ids: frozenset[uuid.UUID]

    @property
    def has_any_role(self) -> bool:
        """이 workspace에서 어떤 위키 역할이든 하나 가졌는지를 나타낸다."""
        return (
            self.is_global_admin
            or bool(self.admin_channel_ids)
            or bool(self.owned_artifact_ids)
        )


def load_wiki_roles(
    db: Session, *, user_id: int, workspace_id: int
) -> WikiRoleContext:
    """이 workspace에서 사용자의 역할 전부를 한 번에 읽는다.

    세 갈래 모두 workspace로 좁힌다. 스냅샷이 "이 workspace에서 무엇인가"를
    말하지 않으면, 남의 workspace 역할이 이쪽 문서 판정에 섞여 든다.
    """
    user_role = wiki_queries.get_user_role(db, user_id)
    admin_channel_ids = frozenset(
        wiki_queries.list_admin_channel_ids(
            db, user_id=user_id, workspace_id=workspace_id
        )
    )
    # 담당 문서도 workspace로 좁힌다. 대상 판정은 문서 id 일치를 다시 보므로
    # 무필터여도 남의 문서를 결정할 자리는 없지만, 스냅샷을 그대로 읽는
    # 소비자(has_any_role 등)는 집합이 비었는지만 본다. 좁히지 않으면 A
    # workspace의 담당자가 B workspace에서도 역할을 가진 사람으로 읽힌다.
    owned_artifact_ids = frozenset(
        wiki_queries.list_owned_artifact_ids(
            db, user_id=user_id, workspace_id=workspace_id
        )
    )
    return WikiRoleContext(
        is_global_admin=user_role == UserRole.ADMIN,
        admin_channel_ids=admin_channel_ids,
        owned_artifact_ids=owned_artifact_ids,
    )


def _is_artifact_admin(
    roles: WikiRoleContext, *, artifact_channel_id: uuid.UUID | None
) -> bool:
    """이 문서에 대해 관리자로 서는지 정한다.

    채널에 놓인 문서는 그 채널의 관리자, 미분류 문서는 전역 ADMIN이다.
    관리자 권한은 채널 단위다 — 전역 ADMIN이라도 채널에 놓인 문서는 그
    채널의 관리자만 연다. 열어 두면 채널 경계가 관리 축에서만 사라진다.
    """
    if artifact_channel_id is None:
        return roles.is_global_admin
    return artifact_channel_id in roles.admin_channel_ids


def can_decide_artifact(
    roles: WikiRoleContext,
    *,
    artifact_channel_id: uuid.UUID | None,
    artifact_id: uuid.UUID,
    owner_user_ids: frozenset[int],
    user_id: int,
) -> bool:
    """이 사용자가 이 문서의 검수 항목을 처리할 수 있는지 정한다.

    담당자가 있는 문서는 담당자 본인만 결정한다. 관리자도 여기서는 서지
    못한다. 관리자는 폴백이지 상위 권한이 아니어서, 열어 두면 담당자의
    결정 영역을 관리자가 언제든 덮어쓸 수 있다.

    담당자가 없는 문서는 이 workspace 구성원이면 누구나 결정한다. 파이프라인이
    만든 문서는 담당자 0명으로 시작하는데, 관리자만 결정할 수 있게 두면
    관리자가 없는 workspace에서는 담당자를 만들 사람도 없어 문서가 영영
    결정되지 않는다. 판정 순서로는 채널 관리자·전역 ADMIN이 그다음
    구성원보다 앞에 서지만, 구성원 폴백이 무조건 통과이므로 결과가 갈리지
    않아 관리자 검사를 따로 두지 않는다.

    구성원인지는 여기서 보지 않는다. 호출자가 workspace 소속을 이미 확인한
    컨텍스트로만 부르므로, 이 자리에서 다시 보면 같은 사실을 두 곳에서
    판정하게 된다. 문서 담당자 지정(can_manage_owners)은 규칙이 달라 관리자
    판정을 그대로 쓴다.

    `artifact_channel_id`는 결정에 쓰지 않지만 인자로 남긴다. 큐 목록과 결정
    경로가 같은 호출 모양을 유지해야, 채널이 판정에 다시 필요해질 때 호출부
    전체를 고치지 않는다.
    """
    if owner_user_ids:
        return (
            artifact_id in roles.owned_artifact_ids
            and user_id in owner_user_ids
        )
    return True


def can_manage_owners(
    roles: WikiRoleContext,
    *,
    artifact_channel_id: uuid.UUID | None,
    artifact_id: uuid.UUID,
    owner_user_ids: frozenset[int],
    user_id: int,
    for_removal: bool,
) -> bool:
    """이 사용자가 이 문서의 담당자 명단을 고칠 수 있는지 정한다.

    검수(can_decide_artifact)와 규칙이 다르다. 검수에서 관리자는 담당자
    없는 문서의 폴백이지만, 담당자 지정에서 관리자는 담당자 유무와 무관하게
    모든 문서를 지정할 수 있고 담당자는 자기 문서에 한한다. 검수의 폴백
    규칙을 여기까지 끌고 오면 담당자가 한 명 생긴 순간 그 문서의 담당자
    명단을 아무도 고칠 수 없게 잠긴다.

    해제는 관리자만이다. 담당자 본인도 못 한다 — 자기 자신을 포함해 명단을
    비울 수 있으면 문서가 조용히 무주공산이 되고, 그 순간 검수 폴백이
    관리자에게 넘어간다. 명단이 줄어드는 방향만 관리자를 거치게 두어
    책임자가 사라지는 일이 감사에 남게 한다.
    """
    if _is_artifact_admin(roles, artifact_channel_id=artifact_channel_id):
        return True
    if for_removal:
        return False
    return artifact_id in roles.owned_artifact_ids and user_id in owner_user_ids
