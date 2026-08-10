"""LLM Wiki의 채널·폴더 관리 HTTP 엔드포인트를 정의한다.

인가가 두 겹인 것은 검수 API와 같지만 첫 겹이 다르다. 표면에 서는 자격은
소속뿐이다(`resolve_member_workspace`) — 채널이 하나도 없는 사람이 첫
채널을 만들 수 있어야 하는데, 검수 자격 게이트를 쓰면 역할이 없어 문
앞에서 막힌다. 대상이 정해지는 핸들러가 "이 채널의 관리자인가"를 다시
본다.

관리자 판정의 출처는 `load_wiki_roles`의 `admin_channel_ids` 하나다.
핸들러마다 channel_admins를 따로 조회하면 검수 쪽 판정과 규칙이 갈릴
자리가 생긴다.

쓰기는 세션으로 직접 한다. 채널·폴더는 불변식이랄 것이 UNIQUE 두 개뿐이라
도메인 서비스를 세울 규모가 아니다. UNIQUE 위반은 예외 문자열을 읽지 않고
제약 이름으로 갈라 409로 옮긴다 — 문구를 파싱하면 드라이버가 문구를 다듬는
순간 계약이 깨진다.

거부는 전부 `deny_reviewer`를 지난다. 막힌 시도가 감사 스트림에 남아야
"누가 남의 채널을 만지려 했나"를 나중에 물을 수 있고, 검수 API와 같은
채널·같은 모양으로 모여야 그 질문이 한 번에 끝난다.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Response
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from catchup.db.dependencies import get_db
from catchup.db.models import Channel
from catchup.db.models import ChannelAdmin
from catchup.db.models import ChannelFolder
from catchup.db.models import KnowledgeArtifact
from catchup.server.knowledge_review.dependencies import MemberContext
from catchup.server.knowledge_review.dependencies import deny_reviewer
from catchup.server.knowledge_review.dependencies import resolve_member_workspace
from catchup.server.knowledge_review.dependencies import review_error
from catchup.server.wiki.roles import load_wiki_roles
from catchup.server.wiki.schemas import ChannelCreateRequest
from catchup.server.wiki.schemas import ChannelListItemResponse
from catchup.server.wiki.schemas import ChannelListResponse
from catchup.server.wiki.schemas import ChannelRenameRequest
from catchup.server.wiki.schemas import ChannelResponse
from catchup.server.wiki.schemas import FolderCreateRequest
from catchup.server.wiki.schemas import FolderRenameRequest
from catchup.server.wiki.schemas import FolderResponse

router = APIRouter(
    prefix="/api/v1/wiki",
    tags=["Wiki Channels"],
)

_CHANNEL_NAME_CONSTRAINT = "uq_channels_workspace_name"
_FOLDER_NAME_CONSTRAINT = "uq_channel_folders_channel_name"
_ARTIFACT_FOLDER_CONSTRAINT = "fk_knowledge_artifacts_folder"


def _violates(error: IntegrityError, constraint: str) -> bool:
    """이 IntegrityError가 그 제약을 어긴 것인지 본다.

    psycopg가 실어 주는 제약 이름만 본다. 없으면 False로 두어 알 수 없는
    위반을 409로 둔갑시키지 않는다 — 그 경우는 500으로 나가 사람이 보게
    하는 편이 낫다.
    """
    constraint_name = getattr(
        getattr(error.orig, "diag", None), "constraint_name", None
    )
    return constraint_name == constraint


def _load_channel(
    db: Session, *, channel_id: uuid.UUID, workspace_id: int
) -> Channel:
    """이 workspace의 채널 하나를 읽는다.

    다른 workspace의 채널은 없는 것으로 답한다. 403으로 가르면 남의
    workspace에 어떤 채널이 있는지를 이 응답으로 떠볼 수 있다.

    Raises:
        HTTPException: 채널이 없으면 404를 던진다.
    """
    channel = db.scalar(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.workspace_id == workspace_id,
        )
    )
    if channel is None:
        raise review_error(
            404,
            code="CHANNEL_NOT_FOUND",
            message="채널을 찾을 수 없습니다.",
        )
    return channel


def _require_channel_admin(
    db: Session, *, channel_id: uuid.UUID, context: MemberContext
) -> Channel:
    """채널을 읽고 그 채널의 관리자인지 확인한다.

    존재 확인이 먼저다. 없는 채널에 403을 주면 소비자는 권한 문제로 읽고
    관리자에게 문의하러 간다.

    Raises:
        HTTPException: 채널이 없으면 404, 관리자가 아니면 403을 던진다.
    """
    channel = _load_channel(
        db, channel_id=channel_id, workspace_id=context.workspace_id
    )
    roles = load_wiki_roles(
        db, user_id=context.user.id, workspace_id=context.workspace_id
    )
    if channel.id not in roles.admin_channel_ids:
        raise deny_reviewer(
            403,
            code="NOT_CHANNEL_ADMIN",
            message="이 채널의 관리자가 아닙니다.",
            user_id=context.user.id,
            workspace_id=context.workspace_id,
        )
    return channel


def _load_folder(
    db: Session, *, folder_id: uuid.UUID, channel_id: uuid.UUID
) -> ChannelFolder:
    """그 채널에 달린 폴더 하나를 읽는다.

    channel_id를 조건에 함께 넣는다. 폴더 id만으로 찾으면 A 채널 관리자가
    경로에 자기 채널을 적고 B 채널의 폴더 id를 실어 남의 폴더를 지울 수
    있다.

    Raises:
        HTTPException: 폴더가 없거나 그 채널의 것이 아니면 404를 던진다.
    """
    folder = db.scalar(
        select(ChannelFolder).where(
            ChannelFolder.id == folder_id,
            ChannelFolder.channel_id == channel_id,
        )
    )
    if folder is None:
        raise review_error(
            404,
            code="FOLDER_NOT_FOUND",
            message="폴더를 찾을 수 없습니다.",
        )
    return folder


@router.post(
    path="/channels",
    response_model=ChannelResponse,
    status_code=201,
    description="위키 채널을 만들고 생성자를 그 채널의 관리자로 세운다.",
)
def create_channel(
    request: ChannelCreateRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ChannelResponse:
    """채널을 만들고 생성자를 관리자로 세운다.

    채널 INSERT와 관리자 INSERT는 한 트랜잭션이다. 나뉘면 관리자가 없는
    채널이 남아, 만든 사람조차 이름을 못 바꾸는 상태가 된다.

    Raises:
        HTTPException: 같은 workspace에 같은 이름이 있으면 409를 던진다.
    """
    channel = Channel(
        workspace_id=context.workspace_id,
        name=request.name,
        created_by=context.user.id,
    )
    db.add(channel)
    try:
        db.flush()
        db.add(
            ChannelAdmin(
                channel_id=channel.id,
                user_id=context.user.id,
                granted_by=context.user.id,
            )
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _CHANNEL_NAME_CONSTRAINT):
            raise review_error(
                409,
                code="CHANNEL_NAME_TAKEN",
                message="같은 이름의 채널이 이미 있습니다.",
            ) from error
        raise

    return ChannelResponse(
        id=str(channel.id),
        name=channel.name,
        workspace_id=channel.workspace_id,
    )


@router.get(
    path="/channels",
    response_model=ChannelListResponse,
    description="이 workspace의 채널을 폴더·문서 수와 함께 조회한다.",
)
def list_channels(
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ChannelListResponse:
    """채널 목록을 폴더 목록·문서 수와 함께 돌려준다.

    구성원이면 workspace의 채널을 전부 본다. 목록을 관리 범위로 좁히는
    일은 이 슬라이스 밖이다 — 채널은 읽는 자리를 고르는 색인이라, 보이지
    않으면 문서를 찾을 길이 없다.
    """
    channels = list(
        db.scalars(
            select(Channel)
            .where(Channel.workspace_id == context.workspace_id)
            .order_by(Channel.created_at, Channel.id)
        ).all()
    )
    roles = load_wiki_roles(
        db, user_id=context.user.id, workspace_id=context.workspace_id
    )

    folders: dict[uuid.UUID, list[FolderResponse]] = {}
    for folder in db.scalars(
        select(ChannelFolder)
        .where(ChannelFolder.workspace_id == context.workspace_id)
        .order_by(ChannelFolder.created_at, ChannelFolder.id)
    ).all():
        folders.setdefault(folder.channel_id, []).append(
            FolderResponse(
                id=str(folder.id),
                name=folder.name,
                channel_id=str(folder.channel_id),
            )
        )

    counts = dict(
        db.execute(
            select(
                KnowledgeArtifact.channel_id,
                func.count(KnowledgeArtifact.id),
            )
            .where(
                KnowledgeArtifact.workspace_id == context.workspace_id,
                KnowledgeArtifact.channel_id.is_not(None),
            )
            .group_by(KnowledgeArtifact.channel_id)
        ).all()
    )

    return ChannelListResponse(
        channels=[
            ChannelListItemResponse(
                id=str(channel.id),
                name=channel.name,
                workspace_id=channel.workspace_id,
                is_admin=channel.id in roles.admin_channel_ids,
                document_count=counts.get(channel.id, 0),
                folders=folders.get(channel.id, []),
            )
            for channel in channels
        ]
    )


@router.patch(
    path="/channels/{channel_id}",
    response_model=ChannelResponse,
    description="채널 이름을 바꾼다. 그 채널의 관리자만 할 수 있다.",
)
def rename_channel(
    channel_id: uuid.UUID,
    request: ChannelRenameRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ChannelResponse:
    """채널 이름을 바꾼다.

    Raises:
        HTTPException: 채널이 없으면 404, 관리자가 아니면 403, 같은 이름이
            이미 있으면 409를 던진다.
    """
    channel = _require_channel_admin(
        db, channel_id=channel_id, context=context
    )
    channel.name = request.name
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _CHANNEL_NAME_CONSTRAINT):
            raise review_error(
                409,
                code="CHANNEL_NAME_TAKEN",
                message="같은 이름의 채널이 이미 있습니다.",
            ) from error
        raise

    return ChannelResponse(
        id=str(channel.id),
        name=channel.name,
        workspace_id=channel.workspace_id,
    )


@router.post(
    path="/channels/{channel_id}/folders",
    response_model=FolderResponse,
    status_code=201,
    description="채널 바로 아래에 폴더를 만든다. 관리자만 할 수 있다.",
)
def create_folder(
    channel_id: uuid.UUID,
    request: FolderCreateRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> FolderResponse:
    """폴더를 만든다.

    workspace_id는 요청이 아니라 채널에서 읽어 채운다. 폴더는 채널과
    (workspace_id, channel_id) 복합 FK로 묶여 있어, 소비자가 준 값을
    믿으면 FK가 깨지거나 남의 workspace 아래에 폴더가 선다.

    Raises:
        HTTPException: 채널이 없으면 404, 관리자가 아니면 403, 같은 이름이
            이미 있으면 409를 던진다.
    """
    channel = _require_channel_admin(
        db, channel_id=channel_id, context=context
    )
    folder = ChannelFolder(
        workspace_id=channel.workspace_id,
        channel_id=channel.id,
        name=request.name,
    )
    db.add(folder)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _FOLDER_NAME_CONSTRAINT):
            raise review_error(
                409,
                code="FOLDER_NAME_TAKEN",
                message="같은 이름의 폴더가 이미 있습니다.",
            ) from error
        raise

    return FolderResponse(
        id=str(folder.id),
        name=folder.name,
        channel_id=str(folder.channel_id),
    )


@router.patch(
    path="/channels/{channel_id}/folders/{folder_id}",
    response_model=FolderResponse,
    description="폴더 이름을 바꾼다. 채널 관리자만 할 수 있다.",
)
def rename_folder(
    channel_id: uuid.UUID,
    folder_id: uuid.UUID,
    request: FolderRenameRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> FolderResponse:
    """폴더 이름을 바꾼다.

    Raises:
        HTTPException: 채널·폴더가 없으면 404, 관리자가 아니면 403, 같은
            이름이 이미 있으면 409를 던진다.
    """
    _require_channel_admin(db, channel_id=channel_id, context=context)
    folder = _load_folder(db, folder_id=folder_id, channel_id=channel_id)
    folder.name = request.name
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _FOLDER_NAME_CONSTRAINT):
            raise review_error(
                409,
                code="FOLDER_NAME_TAKEN",
                message="같은 이름의 폴더가 이미 있습니다.",
            ) from error
        raise

    return FolderResponse(
        id=str(folder.id),
        name=folder.name,
        channel_id=str(folder.channel_id),
    )


@router.delete(
    path="/channels/{channel_id}/folders/{folder_id}",
    status_code=204,
    description="폴더를 지운다. 채널 관리자만 할 수 있다.",
)
def delete_folder(
    channel_id: uuid.UUID,
    folder_id: uuid.UUID,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> Response:
    """폴더를 지운다.

    문서가 든 폴더는 지우지 못한다. 문서가 딸린 FK는 RESTRICT라 DB가
    삭제를 막는데, 그 위반을 잡지 않으면 이 경로만 500으로 나가
    `{"code", "message"}` 계약이 깨진다. "먼저 문서를 옮기라"는 사실을
    소비자가 코드로 읽을 수 있어야 화면이 다음 할 일을 안내한다.

    Raises:
        HTTPException: 채널·폴더가 없으면 404, 관리자가 아니면 403,
            폴더에 문서가 남아 있으면 409를 던진다.
    """
    _require_channel_admin(db, channel_id=channel_id, context=context)
    folder = _load_folder(db, folder_id=folder_id, channel_id=channel_id)
    db.delete(folder)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _ARTIFACT_FOLDER_CONSTRAINT):
            raise review_error(
                409,
                code="FOLDER_NOT_EMPTY",
                message="문서가 있는 폴더는 삭제할 수 없습니다."
                " 문서를 먼저 옮겨 주세요.",
            ) from error
        raise

    return Response(status_code=204)
