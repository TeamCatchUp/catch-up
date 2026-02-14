import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.db.chat_room import get_chat_room
from catchup.db.dependencies import get_db
from catchup.db.models import ChatRoom, User


async def get_valid_chat_room(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ChatRoom | None:
    """채팅방 존재 여부와 사용자의 소유권을 동시에 검증하는 종속성"""
    room = get_chat_room(
        db,
        session_id,
        current_user.id
    )
    
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Chat room not found or access denied."
        )

    return room