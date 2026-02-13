from typing import Optional
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from catchup.db.models import ChatHistory, ChatRoom, SenderType
from catchup.rag.schemas.sources import BaseSource


def get_chat_room(
    db: Session,
    session_id: uuid.UUID
) -> ChatRoom | None:
    return db.scalar(
        select(ChatRoom)
        .where(ChatRoom.session_id == session_id)
    )


def create_chat_room(
    db: Session,
    session_id: uuid.UUID,
    user_id: int,
    workspace_id: int,
    title: str
) -> ChatRoom:
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
    room_id: uuid.UUID,
    role: str,
    content: str,
    sources: Optional[list[BaseSource]]
) -> ChatHistory:
    message = ChatHistory(
        chat_room_id=room_id,
        sender_type=SenderType.HUMAN if role == "user" else SenderType.ASSISTANT,
        content=content,
        sources=sources or []
    )
    db.add(message)
    db.commit()
    return message


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