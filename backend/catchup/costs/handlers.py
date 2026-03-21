import time
import structlog

from catchup.costs.schemas import ChatTokenUsageEvent
from catchup.db.engine import SessionLocal
from catchup.db.models import ChatTokenUsage


logger = structlog.get_logger()

MAX_RETRIES = 3
RETRY_DELAY = 0.5


def chat_token_usage_handler(**kwargs) -> None:
    """
    EventBus로부터 토큰 사용 이벤트를 전달받아
    ChatTokenUsage 테이블에 저장하는 핸들러
    """
    
    raw_event = kwargs.get("event")
    if not raw_event or not isinstance(raw_event, ChatTokenUsageEvent):
        logger.warning(
            "chat_token_usage_handler_event_invalid",
            event=raw_event
        )
        return
    
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with SessionLocal() as db:
                db.add(ChatTokenUsage(**raw_event.model_dump()))
                db.commit()
            return
        except Exception as e:
            last_error = e
            logger.warning(
            "chat_token_usage_save_failed",
                attempt=attempt,
                error=str(e),
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
    
    logger.error(
        "chat_token_usage_dead_letter",
        event=raw_event.model_dump(),
        error=str(last_error),
        exc_info=True
    )