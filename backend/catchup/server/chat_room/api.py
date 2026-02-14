import logging
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.chat.dependencies import get_valid_chat_room
from catchup.chat.schemas import ChatRoomResponse
from catchup.db.chat_room import get_chat_room, get_chat_room_messages, get_chat_rooms
from catchup.db.dependencies import get_db
from catchup.db.models import ChatRoom, User
from catchup.server.chat_room.schemas import ChatHistoryListResponse
from catchup.server.schemas import BasePagination, calculate_skip


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rooms")


@router.get("", response_model=BasePagination[ChatRoomResponse])
def get_rooms(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    skip = calculate_skip(page, size)
    
    items, total = get_chat_rooms(
        db,
        user_id=current_user.id,
        skip = skip,
        limit = size
    )
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": items
    }    
    
    
@router.get("/{session_id}/history", response_model=ChatHistoryListResponse)
def get_room_history(
    session_id: uuid.UUID,
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기 (1 ~ 100)"),
    db: Session = Depends(get_db),
    room: ChatRoom = Depends(get_valid_chat_room)
):
    
    skip = calculate_skip(page, size)
    
    items, total = get_chat_room_messages(
        db,
        room_id=room.id,
        skip=skip,
        limit=size
    )
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": items,
        "title": room.title,
        "session_id": room.session_id
    }