"""검수 루프 API가 서는 자리(누가·어느 workspace)를 확정한다.

이 라우터의 모든 엔드포인트는 "이 workspace의 위키 검토자"만 쓸 수 있다.
그 판정을 핸들러마다 하지 않고 의존성 하나로 모은다. 조회·결정·적용이
같은 문을 지나야, 목록은 보이는데 결정만 막히는 식의 어긋남이 생기지
않는다.

소속·workspace 결정과 오류·감사 헬퍼는 `server.wiki.dependencies`에 있다.
검수는 위키 역할 위에 서는 표면이므로 아래층인 위키 쪽을 가져다 쓴다 —
여기서 다시 정의하면 두 표면의 workspace 결정 규칙이 갈릴 자리가 생긴다.

이 문은 "검수 표면에 설 자격"까지만 본다. 어느 문서를 결정할 수 있는지는
문서마다 갈리므로 대상이 정해지는 핸들러에서 다시 판정한다. 큐 목록을 각자
담당 범위로 좁히는 일은 이 슬라이스 밖이다 — 지금은 역할이 하나라도 있으면
목록 전체가 보인다.

UnitOfWork도 여기서 만든다. `KnowledgeMaintenanceUnitOfWork`는 생성 시점의
workspace_id로 artifact 저장소를 고정하고, mutation 저장소는 호출마다
workspace_id를 받는다. 둘이 어긋나면 타입은 통과하는데 충돌 표시가 남의
workspace 사실로 오염된다. 그래서 workspace_id의 출처를 `ReviewerContext`
하나로 두고, UoW도 그 값에서만 만든다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.orm import Session

from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db.models import User
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.server.wiki.dependencies import deny_reviewer
from catchup.server.wiki.dependencies import get_reviewer_user
from catchup.server.wiki.dependencies import resolve_member_workspace
from catchup.server.wiki.roles import WikiRoleContext
from catchup.server.wiki.roles import load_wiki_roles

ReviewUowFactory = Callable[[], KnowledgeMaintenanceUnitOfWork]


@dataclass(frozen=True, slots=True)
class ReviewerContext:
    """검토자 한 사람이 서 있는 자리를 담는다.

    Attributes:
        user: 인증된 사용자다.
        workspace_id: 이 요청이 다룰 workspace다. 조회·결정·적용이 모두
            이 값 하나만 쓴다.
        reviewer: 결정 저널에 남길 판정자 식별자다. `user:<id>` 형태이며
            DB CHECK가 빈 문자열을 거부하므로 항상 비지 않는다.
        roles: 이 workspace에서의 위키 역할 스냅샷이다. 요청 한 번에 한 번만
            읽어, 핸들러마다 다시 조회하다 판정이 갈리는 일을 막는다.
    """

    user: User
    workspace_id: int
    reviewer: str
    roles: WikiRoleContext


def resolve_reviewer_workspace(
    workspace_id: int | None = None,
    current_user: User = Depends(get_reviewer_user),
    db: Session = Depends(get_db),
) -> ReviewerContext:
    """검토자 컨텍스트를 확정한다.

    소속과 workspace 결정은 `resolve_member_workspace`가 한다. 여기서는
    그 위에 위키 역할(채널 관리자·문서 담당자·전역 ADMIN) 게이트만
    얹는다 — 소속만 있으면 403(NOT_REVIEWER)이다.

    오류 코드 NOT_REVIEWER는 그대로 둔다. 자격의 출처가 권한 행에서 역할로
    바뀌었을 뿐 소비자가 할 일은 같아서, 코드를 바꾸면 화면만 깨진다.

    Raises:
        HTTPException: 소속이나 권한이 없거나, 여러 소속에서 workspace를
            고르지 않았을 때 던진다.
    """
    member = resolve_member_workspace(
        workspace_id=workspace_id, current_user=current_user, db=db
    )
    resolved_workspace_id = member.workspace_id

    roles = load_wiki_roles(
        db, user_id=current_user.id, workspace_id=resolved_workspace_id
    )
    if not roles.has_any_role:
        raise deny_reviewer(
            403,
            code="NOT_REVIEWER",
            message="검수 자격(담당자·관리자)이 없습니다.",
            user_id=current_user.id,
            workspace_id=resolved_workspace_id,
        )

    return ReviewerContext(
        user=current_user,
        workspace_id=resolved_workspace_id,
        reviewer=f"user:{current_user.id}",
        roles=roles,
    )


def get_review_uow_factory(
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
) -> ReviewUowFactory:
    """컨텍스트의 workspace에 묶인 UnitOfWork factory를 만든다.

    factory인 이유는 적용(apply)이 안건 하나를 트랜잭션 하나로 쓰기
    때문이다. 세션 하나를 돌려주면 한 안건의 실패가 앞선 적용까지
    되감는다.

    workspace_id를 인자로 받지 않는다. 받게 두면 핸들러가 UoW와 서비스
    호출에 다른 값을 넘길 수 있고, 그때 충돌 표시가 조용히 오염된다.
    출처를 컨텍스트 하나로 못박아 그 자리를 없앤다.
    """

    def factory() -> KnowledgeMaintenanceUnitOfWork:
        return KnowledgeMaintenanceUnitOfWork(
            SessionLocal, workspace_id=context.workspace_id
        )

    return factory
