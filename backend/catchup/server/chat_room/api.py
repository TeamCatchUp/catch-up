import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.chat.chat_room import process_answer_feedback
from catchup.chat.dependencies import get_valid_chat_room, get_valid_message
from catchup.chat.exceptions import FeedbackImmutableError, LikedWithNegativeFeedbackError
from catchup.chat.schemas import ChatRoomResponse, FeedbackRequest, UserQueryResponse
from catchup.db.chat_room import get_chat_room_messages, get_chat_rooms, get_queries_by_chat_room, get_queries_by_user
from catchup.db.dependencies import get_db
from catchup.db.models import ChatHistory, ChatRoom, User
from catchup.server.chat_room.schemas import ChatHistoryListResponse
from catchup.server.schemas import BasePagination, calculate_skip


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/rooms",
    tags=["Chat Rooms"]   
)


@router.get(
    path="",
    response_model=BasePagination[ChatRoomResponse],
    description="채팅방 목록 조회"
)
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


@router.get(
    path="/queries",
    response_model=BasePagination[UserQueryResponse],
    description="특정 사용자가 모든 채팅방에 걸쳐 남긴 쿼리 목록 조회"
)
def get_query_history_by_user(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기 (1 ~ 100)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    
    skip = calculate_skip(page, size)
    
    items, total =get_queries_by_user(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=size
    )
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": items,
    }


@router.get(
    path="/{session_id}/queries",
    response_model=BasePagination[UserQueryResponse],
    description="특정 채팅방에서 사용자가 남긴 모든 쿼리 목록 조회"
)
def get_query_history_by_room(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기 (1 ~ 100)"),
    db: Session = Depends(get_db),
    room: ChatRoom = Depends(get_valid_chat_room)
):
    skip = calculate_skip(page, size)
    
    items, total = get_queries_by_chat_room(
        db=db,
        room_id=room.id,
        skip=skip,
        limit=size
    )
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": items,
    }

    
@router.get(
    path="/{session_id}/messages",
    response_model=ChatHistoryListResponse,
    description="특정 채팅방 내의 채팅 히스토리 조회"
)
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
    

@router.patch(
    path="/{session_id}/messages/{message_id}/feedback",
    description="답변 피드백 업데이트"
)
async def update_answer_feedback(
    body: FeedbackRequest,
    db: Session = Depends(get_db),
    message: ChatHistory = Depends(get_valid_message),
):
    try:
        updated_message = process_answer_feedback(
            db=db,
            message=message,
            body=body
        )
        
        return {
            "status": "success",
            "message_id": updated_message.id,
            "is_liked": updated_message.is_liked
        }
        
    except FeedbackImmutableError  as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    
    except LikedWithNegativeFeedbackError    as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )