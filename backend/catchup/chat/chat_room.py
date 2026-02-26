import logging
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableWithMessageHistory
from sqlalchemy.orm import Session
from catchup.chat.exceptions import FeedbackImmutableError, LikedWithNegativeFeedbackError
from catchup.chat.schemas import FeedbackRequest
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import LlmProvider, get_llm_service
from catchup.db.chat_room import update_message_feedback
from catchup.db.models import ChatHistory
from catchup.prompts.loader import prompt_loader

logger = logging.getLogger(__name__)

async def generate_chat_room_title(query: str) -> str:
    """채팅방 제목 생성"""
    llm = get_llm_service(LlmProvider.AWS_BEDROCK, ModelCapacity.SMALL).get_llm()
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
    db: Session,
    message: ChatHistory,
    body: FeedbackRequest
):
    if message.is_liked is False:
        raise FeedbackImmutableError("이미 제출된 부정 피드백은 수정할 수 없습니다.")
    
    if body.is_liked is True:
        if body.reasons or body.comment:
            raise LikedWithNegativeFeedbackError("긍정 피드백에 부정 피드백 사유를 포함할 수 없습니다.")

    message = update_message_feedback(
        db=db,
        message=message,
        is_liked=body.is_liked,
        reasons=body.reasons,
        comment=body.comment
    )
    db.commit()
    db.refresh(message)
    
    return message