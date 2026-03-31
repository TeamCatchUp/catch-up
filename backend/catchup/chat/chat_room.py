import structlog
from langchain.messages import AIMessage

from catchup.chat.exceptions import FeedbackImmutableError
from catchup.chat.exceptions import LikedWithNegativeFeedbackError
from catchup.chat.schemas import FeedbackRequest
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import LlmProvider
from catchup.components.llm.factory import get_llm_service
from catchup.costs.schemas import ChatTokenUsageEvent
from catchup.costs.utils import extract_token_usages
from catchup.db.chat_room import update_message_feedback
from catchup.db.engine import SessionLocal
from catchup.db.models import ChatHistory
from catchup.db.models import TokenPurpose
from catchup.events.bus import bus
from catchup.events.enums import EventTopic
from catchup.prompts.loader import prompt_loader
from catchup.rag.schemas.context import GlobalContext

logger = structlog.get_logger()

async def generate_chat_room_title(
    global_context: GlobalContext,
    query: str
) -> str:
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
    
    try:
        raw_response = await llm.ainvoke(input=prompt)

    except Exception as e:
        logger.warning(
            "title_generation_failed",
            fallback="query_truncation",
            error=str(e)
        )
        return query[:30] + "..." if len(query) > 30 else query
    
    raw_title = raw_response.content
    cleaned_title = raw_title.strip().replace('"', '').replace("'", "")
    
    _emit_title_generation_token_usage_event(
        global_context=global_context,
        raw_response=raw_response
    )

    return cleaned_title[:25]


def _emit_title_generation_token_usage_event(
    global_context: GlobalContext,
    raw_response: AIMessage,
) -> None:
    """
    채팅방 제목 생성으로 인해 발생한 토큰 사용 이벤트를 발행한다.
    """
    token_breakdown = extract_token_usages(raw_response).get("token_breakdown", {})
    bus.emit(
        topic=EventTopic.COST,
        event=ChatTokenUsageEvent(
            user_id=global_context.user.id,
            workspace_id=global_context.workspace.id,
            company_id=global_context.company.id,
            purpose=TokenPurpose.TITLE_GENERATION,
            token_breakdown=token_breakdown,
        )
    )


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