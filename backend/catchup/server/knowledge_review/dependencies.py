"""검수 루프 API가 서는 자리(누가·어느 workspace)를 확정한다.

이 라우터의 모든 엔드포인트는 "이 workspace의 위키 검토자"만 쓸 수 있다.
그 판정을 핸들러마다 하지 않고 의존성 하나로 모은다. 조회·결정·적용이
같은 문을 지나야, 목록은 보이는데 결정만 막히는 식의 어긋남이 생기지
않는다.

workspace는 쿼리 파라미터를 믿지 않는다. 준 값이라도 소속(UserWorkspace)과
검토자 권한(WikiReviewerGrant)을 둘 다 통과해야 하고, 주지 않으면 소속이
하나일 때만 그것으로 정한다. 여러 곳에 속한 사람에게 임의로 하나를 골라
주면 남의 workspace 문서를 자기 것으로 착각한 채 결정할 자리가 생긴다.

거부도 감사 기록이다. 막힌 시도가 남지 않으면 감사 스트림은 통과한 결정만
담아, "누가 어느 workspace를 들여다보려 했나"를 나중에 물을 수 없다. 그래서
거부는 전부 `deny_reviewer`를 지나며 감사 이벤트를 하나 낸다.

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
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.audit.actions import KnowledgeReviewAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.emitters import emit_audit_event
from catchup.audit.metadata import KnowledgeReviewAuditMetadata
from catchup.auth.dependencies import cookie_scheme
from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db.models import User
from catchup.db.models import UserWorkspace
from catchup.db.models import WikiReviewerGrant
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)

ReviewUowFactory = Callable[[], KnowledgeMaintenanceUnitOfWork]


def review_error(status_code: int, *, code: str, message: str) -> HTTPException:
    """검수 API의 표준 오류를 만든다.

    detail을 `{"code", "message"}`로 고정한다. 소비자가 코드로 분기하고
    문구는 사람에게 보여 주기만 하도록 나눈 것이다. 내부 예외 문자열은
    절대 담지 않는다 — 변경안 식별자나 저장소 사정이 그대로 새어 나가면
    오류 응답이 내부 구조를 설명하는 문서가 된다.
    """
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def deny_reviewer(
    status_code: int,
    *,
    code: str,
    message: str,
    user_id: int,
    workspace_id: int | None,
) -> HTTPException:
    """인가 거부를 감사 스트림에 남기고 표준 오류를 만든다.

    `audit_log` 데코레이터는 핸들러가 실행되는 동안의 예외만 본다. 인가
    거부는 의존성에서 끝나 핸들러에 닿지 않으므로, 그 경로만 감사 기록이
    비어 막힌 시도가 남지 않는다. 그래서 여기서 감사 이벤트를 직접 낸다 —
    로거를 따로 만들지 않고 `emit_audit_event`를 쓰는 이유는 성공한 결정과
    같은 채널·같은 모양으로 한 스트림에 모여야 하기 때문이다.
    """
    emit_audit_event(
        action=KnowledgeReviewAction.AUTHORIZE,
        status=AuditStatus.FAILURE,
        level=AuditLevel.WARNING,
        metadata=KnowledgeReviewAuditMetadata(
            context=code,
            user_id=user_id,
            workspace_id=workspace_id,
        ),
    )
    return review_error(status_code, code=code, message=message)


def get_reviewer_user(
    access_token: str = Depends(cookie_scheme),
    db: Session = Depends(get_db),
) -> User:
    """인증된 사용자를 이 라우터의 오류 계약에 맞춰 돌려준다.

    `get_current_user`를 그대로 쓰지 않고 감싼다. 그쪽은 401 detail을 사람이
    읽는 문자열로 던지는데, 이 라우터는 전 응답의 detail이
    `{"code", "message"}`라고 약속했다. 소비자가 가장 자주 만나는 오류가
    세션 만료이므로, 하필 그 응답만 모양이 달라 코드로 분기할 수 없으면
    약속이 무의미해진다.

    감싸는 쪽을 고친 이유는 `get_current_user`가 다른 라우터 전체의 계약이기
    때문이다. 거기를 바꾸면 이 슬라이스와 무관한 소비자의 오류 처리가
    함께 깨진다.

    `Depends`가 아니라 직접 호출한다. 하위 의존성의 예외는 이 함수가 실행되기
    전에 이미 밖으로 나가므로, `Depends(get_current_user)`로는 잡을 자리가
    없다.

    Raises:
        HTTPException: 쿠키가 없거나 토큰이 유효하지 않으면 401을 던진다.
    """
    try:
        return get_current_user(access_token=access_token, db=db)
    except HTTPException as error:
        if error.status_code != 401:
            raise
        # 원래 문구는 버린다. 쿠키 없음·만료·없는 사용자를 가려 알려 주면
        # 로그인하지 않은 상대에게 계정 존재 여부를 흘리게 된다.
        raise review_error(
            401,
            code="UNAUTHENTICATED",
            message="로그인이 필요합니다.",
        ) from error


@dataclass(frozen=True, slots=True)
class ReviewerContext:
    """검토자 한 사람이 서 있는 자리를 담는다.

    Attributes:
        user: 인증된 사용자다.
        workspace_id: 이 요청이 다룰 workspace다. 조회·결정·적용이 모두
            이 값 하나만 쓴다.
        reviewer: 결정 저널에 남길 판정자 식별자다. `user:<id>` 형태이며
            DB CHECK가 빈 문자열을 거부하므로 항상 비지 않는다.
    """

    user: User
    workspace_id: int
    reviewer: str


def resolve_reviewer_workspace(
    workspace_id: int | None = None,
    current_user: User = Depends(get_reviewer_user),
    db: Session = Depends(get_db),
) -> ReviewerContext:
    """검토자 컨텍스트를 확정한다.

    workspace_id를 안 주면 사용자의 소속이 하나일 때 그것을 쓴다.
    여러 곳이면 명시를 요구한다(400). 준 값은 소속(UserWorkspace)과
    검토자 권한(WikiReviewerGrant)을 모두 통과해야 한다 — 소속만
    있으면 403(NOT_REVIEWER), 소속이 없으면 403(NOT_MEMBER).

    Raises:
        HTTPException: 소속이나 권한이 없거나, 여러 소속에서 workspace를
            고르지 않았을 때 던진다.
    """
    memberships = list(
        db.scalars(
            select(UserWorkspace.workspace_id)
            .where(UserWorkspace.user_id == current_user.id)
            .order_by(UserWorkspace.workspace_id)
        ).all()
    )

    if workspace_id is None:
        if not memberships:
            raise deny_reviewer(
                403,
                code="NOT_MEMBER",
                message="속한 워크스페이스가 없습니다.",
                user_id=current_user.id,
                workspace_id=None,
            )
        if len(memberships) > 1:
            raise deny_reviewer(
                400,
                code="WORKSPACE_REQUIRED",
                message="여러 워크스페이스에 속해 있어 workspace_id가"
                " 필요합니다.",
                user_id=current_user.id,
                workspace_id=None,
            )
        resolved_workspace_id = memberships[0]
    else:
        if workspace_id not in memberships:
            # 소속을 먼저 본다. 권한 없음보다 소속 없음이 먼저 걸려야
            # "남의 workspace에 검토자 권한이 있는지"를 이 응답으로
            # 떠볼 수 없다.
            raise deny_reviewer(
                403,
                code="NOT_MEMBER",
                message="해당 워크스페이스의 구성원이 아닙니다.",
                user_id=current_user.id,
                workspace_id=workspace_id,
            )
        resolved_workspace_id = workspace_id

    granted = db.scalar(
        select(WikiReviewerGrant.user_id).where(
            WikiReviewerGrant.user_id == current_user.id,
            WikiReviewerGrant.workspace_id == resolved_workspace_id,
        )
    )
    if granted is None:
        raise deny_reviewer(
            403,
            code="NOT_REVIEWER",
            message="위키 검토자 권한이 없습니다.",
            user_id=current_user.id,
            workspace_id=resolved_workspace_id,
        )

    return ReviewerContext(
        user=current_user,
        workspace_id=resolved_workspace_id,
        reviewer=f"user:{current_user.id}",
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
