import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.chat.schemas import ChatRoomResponse
from catchup.db.chat_room import get_chat_rooms
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.server.schemas import BasePagination


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.get("/rooms", response_model=BasePagination[ChatRoomResponse])
def get_rooms(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    skip = (page - 1) * size
    
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
    