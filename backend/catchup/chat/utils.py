import uuid
from langchain.messages import AIMessage, HumanMessage
from langchain_core.messages import BaseMessage
from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.db.chat_room import get_recent_messages
from catchup.db.models import SenderType


def restore_conversation_context(
    db: Session,
    session_id: uuid.UUID,
) -> list[BaseMessage]:
    """
    DB에서 최근 대화를 로드하여 Langchain 메시지 객체 리스트로 반환한다.
    """
    
    recent_messages = get_recent_messages(
        db=db,
        session_id=session_id
    )
    
    converted_messages: list[BaseMessage] = []
    
    if recent_messages:
        recent_messages.reverse()
        
        for message in recent_messages:
            if message.sender_type == SenderType.HUMAN:
                converted_messages.append(HumanMessage(content=message.content))
            else:
                converted_messages.append(AIMessage(content=message.content))
                    
    return converted_messages