import logging

from langchain_core.output_parsers import StrOutputParser

from catchup.chat.exceptions import FeedbackImmutableError
from catchup.chat.exceptions import LikedWithNegativeFeedbackError
from catchup.chat.schemas import FeedbackRequest
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import LlmProvider
from catchup.components.llm.factory import get_llm_service
from catchup.db.chat_room import update_message_feedback
from catchup.db.engine import SessionLocal
from catchup.db.models import ChatHistory
from catchup.prompts.loader import prompt_loader

logger = logging.getLogger(__name__)

async def generate_chat_room_title(query: str) -> str:
    """채팅방 제목 생성"""
    llm = get_llm_service(
        LlmProvider.AWS_BEDROCK, 
        ModelCapacity.SMALL,
        streaming=False
    ).get_llm()
    
    prompt = prompt_loader.get_prompt(
        "chat/summarize_title.j2",
        query=query
    )
    
    chain = llm | StrOutputParser()
    
    try:
        generated_title = await chain.ainvoke(input=prompt)
        cleaned_title = generated_title.strip().replace('"', '').replace("'", "")
        return cleaned_title[:25]

    except Exception as e:
        logger.warning(f"Failed to generate chat room title from query: {e}")
        return query[:30] + "..." if len(query) > 30 else query
    

def process_answer_feedback(
    message_id: int,
    body: FeedbackRequest
):
    with SessionLocal() as db:
        message = db.get(ChatHistory, message_id)
        
        if message.is_liked is False:
            raise FeedbackImmutableError("이미 제출된 부정 피드백은 수정할 수 없습니다.")
        
        if body.is_liked is True:
            if body.reasons or body.comment:
                raise LikedWithNegativeFeedbackError("긍정 피드백에 부정 피드백 사유를 포함할 수 없습니다.")

        message = update_message_feedback(
            message=message,
            is_liked=body.is_liked,
            reasons=body.reasons,
            comment=body.comment
        )
        db.commit()
        db.refresh(message)
    
    return message