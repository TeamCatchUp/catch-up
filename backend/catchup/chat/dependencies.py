import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.db.chat_room import get_chat_room, get_message
from catchup.db.dependencies import get_db
from catchup.db.models import ChatHistory, ChatRoom, User


async def get_valid_chat_room(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ChatRoom:
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


async def get_valid_message(
    message_id: int,
    room: ChatRoom = Depends(get_valid_chat_room),
    db: Session = Depends(get_db)
) -> ChatHistory:
    """메시지 존재 여부, 채팅방 귀속 여부, 사용자 소유권 검증"""
    
    message = get_message(
        db=db,
        room_id=room.id,
        message_id=message_id
    )
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found."
        )
    
    return message    