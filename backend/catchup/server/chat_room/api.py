import logging
from typing import Optional
import uuid

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.chat.chat_room import process_answer_feedback
from catchup.chat.dependencies import get_valid_chat_room
from catchup.chat.dependencies import get_valid_message
from catchup.chat.dependencies import get_valid_user_query
from catchup.chat.exceptions import FeedbackImmutableError
from catchup.chat.exceptions import LikedWithNegativeFeedbackError
from catchup.chat.schemas import ChatHistoryResponse
from catchup.chat.schemas import ChatRoomResponse
from catchup.chat.schemas import FeedbackRequest
from catchup.chat.schemas import UserQueryResponse
from catchup.chat.schemas import UserQueryWithSaveStatusResponse
from catchup.db.chat_room import get_chat_room_messages
from catchup.db.chat_room import get_chat_rooms
from catchup.db.chat_room import get_queries_by_chat_room
from catchup.db.chat_room import get_queries_by_user
from catchup.db.chat_room import get_queries_with_save_status
from catchup.db.chat_room import get_query_answer_pair
from catchup.db.chat_room import toggle_save_status
from catchup.db.dependencies import get_db
from catchup.db.models import ChatHistory
from catchup.db.models import ChatRoom
from catchup.db.models import User
from catchup.observability.langfuse.feedback import upsert_feedback
from catchup.server.chat_room.schemas import ChatHistoryListResponse
from catchup.server.schemas import BasePagination
from catchup.server.schemas import calculate_skip
from catchup.configs.config import settings

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
    message: ChatHistory = Depends(get_valid_message),
):
    try:
        updated_message = await run_in_threadpool(
            process_answer_feedback,
            message_id=message.id,
            body=body
        )
        
        if settings.ENABLE_LANGFUSE:
            trace_id = message.trace_id
            await upsert_feedback(
                trace_id=trace_id,
                content=body.model_dump(exclude_none=True)
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


@router.patch(
    path="/{session_id}/messages/{message_id}/saves",
    description="어시스턴트 답변 저장 상태 토글"
)
def update_answer_saved_status(
    db: Session = Depends(get_db),
    message: ChatHistory = Depends(get_valid_message)
):
    updated_message = toggle_save_status(
        db=db,
        message=message
    )
    db.commit()
    
    return {
        "status": "success",
        "message_id": updated_message.id
    }


@router.get(
    path="/queries/saved-status",
    response_model=BasePagination[UserQueryWithSaveStatusResponse],
    description="(마이페이지) 답변 저장 여부를 포함하여 특정 사용자가 남긴 모든 쿼리 목록 조회"
)
def get_query_history_with_status(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="검색어 (질문 내용)"),
    is_saved: Optional[bool] = Query(None, description="저장 여부 (true/false)"),
    sort: str = Query("desc", pattern="^(asc|desc)$", description="정렬: asc(오래된순), desc(최신순)"),
    period: str = Query("all", description="조회 기간: today, 7d, all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    skip = calculate_skip(page, size)
    
    items, total = get_queries_with_save_status(
        db=db,
        user_id=current_user.id,
        search_term=search,
        period=period,
        is_saved=is_saved,
        sort=sort,
        skip=skip,
        limit=size
    )
    
    return {
        "total": total, 
        "page": page, 
        "size": size, 
        "items": items
    }


@router.get(
    path="/queries/{message_id}/detail",
    response_model=list[ChatHistoryResponse],
    description="마이페이지 질문 히스토리에서 특정 질문 클릭 시 질문-답변 세트 상세 조회"
)
def get_query_detail(
    db: Session = Depends(get_db),
    query: ChatHistory = Depends(get_valid_user_query)
):
    pair = get_query_answer_pair(db, query)
    return pair