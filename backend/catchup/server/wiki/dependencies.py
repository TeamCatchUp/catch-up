"""위키 표면이 서는 자리(누가·어느 workspace)와 공통 오류 계약을 모은다.

위키 API와 검수 API는 같은 오류 모양과 같은 workspace 결정 규칙을 쓴다.
검수는 그 위에 역할 게이트를 한 겹 더 얹은 표면이므로, 아래층인 위키
패키지가 공통 재료를 갖고 검수가 그것을 가져다 쓴다. 반대 방향으로 두면
채널·폴더 관리가 검수 패키지를 import하게 되어, 의존 방향이 의미와
어긋난다.

workspace는 쿼리 파라미터를 믿지 않는다. 준 값이라도 소속(UserWorkspace)을
통과해야 하고, 주지 않으면 소속이 하나일 때만 그것으로 정한다. 여러 곳에
속한 사람에게 임의로 하나를 골라 주면 남의 workspace 문서를 자기 것으로
착각한 채 결정할 자리가 생긴다.

거부도 감사 기록이다. 막힌 시도가 남지 않으면 감사 스트림은 통과한 결정만
담아, "누가 어느 workspace를 들여다보려 했나"를 나중에 물을 수 없다. 그래서
거부는 전부 `deny_reviewer`를 지나며 감사 이벤트를 하나 낸다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session

from catchup.audit.actions import KnowledgeReviewAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.emitters import emit_audit_event
from catchup.audit.metadata import KnowledgeReviewAuditMetadata
from catchup.auth.dependencies import cookie_scheme
from catchup.auth.dependencies import get_current_user
from catchup.db import wiki as wiki_queries
from catchup.db.dependencies import get_db
from catchup.db.models import User


def review_error(
    status_code: int,
    *,
    code: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> HTTPException:
    """위키·검수 API의 표준 오류를 만든다.

    detail을 `{"code", "message"}`로 고정한다. 소비자가 코드로 분기하고
    문구는 사람에게 보여 주기만 하도록 나눈 것이다. 내부 예외 문자열은
    절대 담지 않는다 — 변경안 식별자나 저장소 사정이 그대로 새어 나가면
    오류 응답이 내부 구조를 설명하는 문서가 된다.

    `extra`는 그 두 키 위에 얹는 구조화된 재료다. 소비자가 화면을 고치려면
    코드만으로 부족한 경우가 있다 — 미결정 블록 번호가 그렇다. 사람이 읽는
    문구에 섞어 넣으면 소비자가 문구를 파싱하게 되므로 키를 따로 세운다.
    code·message는 덮어쓰지 못한다.

    code는 예외 객체에도 붙인다. `audit_log`는 예외의 `code` 속성만 읽어
    감사 기록의 context를 채우므로, detail에만 담으면 404·409로 끝난
    요청의 실패 기록에 이유가 남지 않는다.
    """
    detail: dict[str, Any] = dict(extra or {})
    detail["code"] = code
    detail["message"] = message
    error = HTTPException(
        status_code=status_code,
        detail=detail,
    )
    error.code = code
    return error


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
    """인증된 사용자를 이 표면의 오류 계약에 맞춰 돌려준다.

    `get_current_user`를 그대로 쓰지 않고 감싼다. 그쪽은 401 detail을 사람이
    읽는 문자열로 던지는데, 위키·검수 라우터는 전 응답의 detail이
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
class MemberContext:
    """소속만 확인된 사용자가 서 있는 자리를 담는다.

    Attributes:
        user: 인증된 사용자다.
        workspace_id: 이 요청이 다룰 workspace다.
    """

    user: User
    workspace_id: int


def resolve_member_workspace(
    workspace_id: int | None = None,
    current_user: User = Depends(get_reviewer_user),
    db: Session = Depends(get_db),
) -> MemberContext:
    """소속만 보고 workspace를 확정한다.

    workspace_id를 안 주면 사용자의 소속이 하나일 때 그것을 쓴다. 여러
    곳이면 명시를 요구한다(400). 준 값은 소속(UserWorkspace)을 통과해야
    한다 — 아니면 403(NOT_MEMBER)이다.

    역할 게이트가 없다는 것이 이 문의 요점이다. 채널·폴더 관리처럼
    "구성원이면 누구나 서고, 대상마다 관리자인지 다시 본다"는 표면은
    검수 자격(NOT_REVIEWER)으로 막으면 안 된다 — 아직 채널이 하나도 없는
    사람은 어떤 역할도 없어 채널을 만들 문 앞에서 막힌다.

    Raises:
        HTTPException: 소속이 없거나, 여러 소속에서 workspace를 고르지
            않았을 때 던진다.
    """
    memberships = wiki_queries.list_membership_workspace_ids(
        db, current_user.id
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
            # "남의 workspace에 권한이 있는지"를 이 응답으로 떠볼 수 없다.
            raise deny_reviewer(
                403,
                code="NOT_MEMBER",
                message="해당 워크스페이스의 구성원이 아닙니다.",
                user_id=current_user.id,
                workspace_id=workspace_id,
            )
        resolved_workspace_id = workspace_id

    return MemberContext(
        user=current_user, workspace_id=resolved_workspace_id
    )
