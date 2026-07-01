import uuid

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.db.chat_room import get_chat_room
from catchup.db.chat_room import get_message
from catchup.db.chat_room import get_user_message_with_ownership
from catchup.db.dependencies import get_db
from catchup.db.models import ChatHistory
from catchup.db.models import ChatRoom
from catchup.db.models import User
from catchup.db.models import UserRole
from catchup.db.user_prompt_settings import get_user_prompt_settings
from catchup.db.users import get_user_with_full_context
from catchup.schemas.context import GlobalCompanyContext
from catchup.schemas.context import GlobalContext
from catchup.schemas.context import GlobalUserContext
from catchup.schemas.context import GlobalWorkspaceContext
from catchup.schemas.prompt_settings import PromptSettings


async def get_valid_chat_room(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatRoom:
    """채팅방 존재 여부와 사용자의 소유권을 동시에 검증하는 종속성"""
    room = get_chat_room(db, session_id, current_user.id)

    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat room not found or access denied.",
        )

    return room


async def get_valid_message(
    message_id: int,
    room: ChatRoom = Depends(get_valid_chat_room),
    db: Session = Depends(get_db),
) -> ChatHistory:
    """메시지 존재 여부, 채팅방 귀속 여부, 사용자 소유권 검증"""
    message = get_message(db=db, room_id=room.id, message_id=message_id)

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )

    return message


async def get_valid_user_query(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatHistory:
    is_admin = current_user.role == UserRole.ADMIN

    message = get_user_message_with_ownership(
        db=db,
        message_id=message_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="질문 메시지를 찾을 수 없거나 접근 권한이 없습니다.",
        )
    return message


async def get_rag_global_context(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db),
) -> GlobalContext:
    db_user_full = get_user_with_full_context(db_session, current_user.id)

    if not db_user_full:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User context not found"
        )

    if not db_user_full.workspace_links:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any workspace",
        )

    # TODO: 향후 클라이언트에서 전달받은 workspace_id로 매칭하는 로직 추가
    target_workspace = db_user_full.workspace_links[0].workspace

    if not target_workspace.company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company context not found for this workspace",
        )

    return GlobalContext(
        user=GlobalUserContext.model_validate(db_user_full),
        workspace=GlobalWorkspaceContext.model_validate(target_workspace),
        company=GlobalCompanyContext.model_validate(target_workspace.company),
    )


async def get_prompt_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PromptSettings:
    settings = get_user_prompt_settings(db=db, user_id=current_user.id)
    if settings is None:
        return PromptSettings()
    return PromptSettings.model_validate(settings)
