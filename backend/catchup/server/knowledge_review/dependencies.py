"""검수 루프 API가 서는 자리(누가·어느 workspace)를 확정한다.

문은 두 개다. 큐 목록·상세도, 판정(블록 결정·발행·승인·반려)도 이
workspace에 속하기만 하면 지난다. 이름을 둘로 나눠 둔 것은 열람과 판정이
서로 다른 문을 가리키게 해, 나중에 판정 경로에만 조건을 더할 때 열람이
함께 바뀌지 않게 하기 위해서다.

두 문 모두 판정을 핸들러마다 하지 않고 의존성으로 모은다. 문이 하나씩
정해져 있어야 라우트마다 다른 규칙이 조용히 생기는 자리를 없앨 수 있다.

소속·workspace 결정과 오류·감사 헬퍼는 `server.wiki.dependencies`에 있다.
검수는 위키 역할 위에 서는 표면이므로 아래층인 위키 쪽을 가져다 쓴다 —
여기서 다시 정의하면 두 표면의 workspace 결정 규칙이 갈릴 자리가 생긴다.

두 문 다 "이 표면에 설 자격"까지만 본다. 어느 문서를 결정할 수 있는지는
문서마다 갈리므로 대상이 정해지는 핸들러에서 다시 판정한다. 큐 목록을 각자
담당 범위로 좁히는 일은 이 슬라이스 밖이다. 지금은 workspace 구성원이면
목록 전체가 보이고, 줄마다 결정 가능 여부만 can_review로 표시한다.

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
    """판정 경로가 설 검토자 컨텍스트를 확정한다.

    소속과 workspace 결정은 `resolve_member_workspace`가 한다. 그 위에 역할
    게이트를 얹지 않는다. 담당자가 없는 문서는 workspace 구성원 누구나
    결정하므로, 역할 하나 없는 사람을 이 문에서 미리 끊으면 그 폴백에
    닿을 수 없다. 누가 어느 문서를 결정할 수 있는지는 대상이 정해지는
    핸들러가 `can_decide_artifact`로 다시 본다.

    소속 확인은 그대로 남는다. 구성원 폴백의 범위가 workspace이므로, 여기가
    열리면 담당자 없는 문서가 바깥 사람에게까지 열린다. 소속 없는 요청의
    403 코드는 `resolve_member_workspace`가 정하는 NOT_MEMBER다.

    열람 경로와 결정 규칙이 같아졌지만 문은 둘로 남긴다. 두 경로가 서로
    다른 이름을 가리켜야 나중에 판정 경로에만 조건을 더할 때 열람이 함께
    바뀌지 않는다.

    Raises:
        HTTPException: 소속이 없거나, 여러 소속에서 workspace를 고르지
            않았을 때 던진다.
    """
    return resolve_member_reviewer_context(
        workspace_id=workspace_id, current_user=current_user, db=db
    )


def resolve_member_reviewer_context(
    workspace_id: int | None = None,
    current_user: User = Depends(get_reviewer_user),
    db: Session = Depends(get_db),
) -> ReviewerContext:
    """열람 전용 컨텍스트를 확정한다.

    소속과 workspace 결정은 `resolve_member_workspace`가 하고, 위키 역할은
    읽기만 한다. 역할이 하나도 없어도 통과시키는 것이 이 문의 요점이다.
    검토 큐는 팀이 함께 보는 목록이라, 담당자가 아니라는 이유로 무엇이
    올라와 있는지조차 볼 수 없게 하면 검토가 담당자 개인의 일이 된다.

    역할을 그래도 읽는 이유는 응답의 can_review 때문이다. 줄마다 결정할 수
    있는지 표시하려면 역할 스냅샷이 필요하고, 요청 한 번에 한 번만 읽어야
    같은 응답 안에서 판정이 갈리지 않는다.

    Raises:
        HTTPException: 소속이 없거나, 여러 소속에서 workspace를 고르지
            않았을 때 던진다.
    """
    member = resolve_member_workspace(
        workspace_id=workspace_id, current_user=current_user, db=db
    )
    roles = load_wiki_roles(
        db, user_id=current_user.id, workspace_id=member.workspace_id
    )
    return ReviewerContext(
        user=current_user,
        workspace_id=member.workspace_id,
        reviewer=f"user:{current_user.id}",
        roles=roles,
    )


def _uow_factory_for(context: ReviewerContext) -> ReviewUowFactory:
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


def get_review_uow_factory(
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
) -> ReviewUowFactory:
    """판정 경로가 쓸 UnitOfWork factory를 만든다.

    판정 경로의 문을 지난 컨텍스트에서만 workspace_id를 가져온다.
    """
    return _uow_factory_for(context)


def get_member_review_uow_factory(
    context: ReviewerContext = Depends(resolve_member_reviewer_context),
) -> ReviewUowFactory:
    """열람 경로가 쓸 UnitOfWork factory를 만든다.

    factory를 만드는 방식은 판정 경로와 같고 컨텍스트의 출처만 다르다.
    열람이 판정 경로의 컨텍스트를 빌려 쓰면, 판정에만 조건을 더하는 순간
    목록까지 같이 닫힌다.
    """
    return _uow_factory_for(context)
