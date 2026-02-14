from typing import Optional
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from catchup.chat.schemas import FeedbackRequest
from catchup.db.models import ChatHistory, ChatRoom, SenderType
from catchup.rag.schemas.sources import BaseSource


def get_chat_room(
    db: Session,
    session_id: uuid.UUID,
    user_id: int
) -> ChatRoom | None:
    """사용자 권한 확인을 포함한 세션 ID 기반 단일 채팅방 조회"""
    
    # 세션 ID 검증 및 사용자 권한 확인
    filter_query = (
        (ChatRoom.session_id == session_id) & 
        (ChatRoom.user_id == user_id)
    )
    
    return db.scalar(
        select(ChatRoom)
        .where(filter_query)
    )


def get_chat_rooms(
    db: Session,
    user_id: int,
    skip: int = 0,  # 앞에서 몇 개 건너뛸지
    limit: int = 20  # 몇 개 갸져올지
) -> tuple[list[ChatRoom], int]:  # (목록, 전체 개수)
    """채팅방 목록 조회"""
    
    filter_query = (ChatRoom.user_id == user_id)
    
    total_count = db.scalar(
        select(func.count())
        .select_from(ChatRoom)
        .where(filter_query)
    ) or 0
        
    stmt = (
        select(ChatRoom)
        .where(filter_query)
        .order_by(ChatRoom.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    items = db.scalars(stmt).all()
    
    return list(items), total_count


def create_chat_room(
    db: Session,
    session_id: uuid.UUID,
    user_id: int,
    workspace_id: int,
    title: str
) -> ChatRoom:
    """채팅방 생성"""
    room = ChatRoom(
        session_id=session_id,
        user_id=user_id,
        workspace_id=workspace_id,
        title=title
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    
    return room


def add_message(
    db: Session,
    room_id: int,
    role: str,
    content: str,
    sources: Optional[list[BaseSource]]
) -> ChatHistory:
    """채팅 메시지 저장"""
    message = ChatHistory(
        chat_room_id=room_id,
        sender_type=SenderType.HUMAN if role == "user" else SenderType.ASSISTANT,
        content=content,
        sources=sources or []
    )
    db.add(message)
    db.commit()
    return message


def get_chat_room_messages(
    db: Session,
    room_id: int,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[ChatHistory], int]:
    """채팅 메시지 히스토리 조회"""
    
    filter_query = (
        (ChatHistory.chat_room_id == room_id) &
        (ChatHistory.is_displayed == True)
    )
        
    total_count = db.scalar(
        select(func.count())
        .select_from(ChatHistory)
        .where(filter_query)
    ) or 0
    
    stmt = (
        select(ChatHistory)
        .where(filter_query)
        .order_by(ChatHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    items = db.scalars(stmt).all()
    
    return list(reversed(items)), total_count


def get_queries_by_user(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[ChatHistory], int]:
    
    """특정 사용자가 모든 채팅방에서 작성한 쿼리만 전체 조회 (최신 순)"""
    
    filter_query = (
        (ChatRoom.user_id == user_id) &
        (ChatHistory.sender_type == SenderType.HUMAN) &
        (ChatHistory.is_displayed == True)
    )
    
    total_count = db.scalar(
        select(func.count())
        .select_from(ChatHistory)
        .join(ChatRoom, ChatHistory.chat_room_id == ChatRoom.id)
        .where(filter_query)
    ) or 0
    
    stmt = (
        select(ChatHistory)
        .join(ChatRoom, ChatHistory.chat_room_id == ChatRoom.id)
        .options(joinedload(ChatHistory.chat_room))
        .where(filter_query)
        .order_by(ChatHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    items = db.scalars(stmt).all()
    
    return list(items), total_count


def get_queries_by_chat_room(
    db: Session,
    room_id: int,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[ChatHistory], int]:
    """특정 채팅방 내에서 사용자가 작성한 쿼리만 조회 (최신 순)"""
    filter_query = (
        (ChatHistory.chat_room_id == room_id) &
        (ChatHistory.sender_type == SenderType.HUMAN) &
        (ChatHistory.is_displayed == True)
    )
    
    total_count = db.scalar(
        select(func.count())
        .select_from(ChatHistory)
        .where(filter_query)
    ) or 0
    
    stmt = (
        select(ChatHistory)
        .where(filter_query)
        .order_by(ChatHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    items = db.scalars(stmt).all()
    
    return list(items), total_count


def get_message(
    db: Session,
    room_id: int,
    message_id: int
) -> ChatHistory:
    """단일 메세지 조회"""
    
    stmt = (
        select(ChatHistory)
        .where(
            (ChatHistory.id == message_id) &
            (ChatHistory.chat_room_id == room_id)
        )
    )
    return db.scalar(stmt)


def update_message_feedback(
    db: Session,
    message: ChatHistory,
    is_liked: Optional[bool] = None,
    reasons: Optional[list[str]] = None,
    comment: Optional[str] = None,
) -> ChatHistory:
    message.is_liked = is_liked
    
    if is_liked is False:
        message.feedback_reasons = reasons
        message.feedback_comment = comment
    
    db.add(message)
    db.commit()
    db.refresh(message)
    
    return message