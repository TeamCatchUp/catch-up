from typing import Optional
import uuid
from sqlalchemy import select
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