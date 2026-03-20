from catchup.costs.contexts.chat import ChatTokenUsageContext
from catchup.costs.schemas import ChatTokenUsageEvent
from catchup.events.bus import bus
from catchup.events.enums import EventTopic


def emit_chat_token_usage_event(
    user_id: int,
    workspace_id: int,
    company_id: int,
) -> None:
    """
    Chat 토큰 사용 이벤트 Emitter.
    응답 완료 후 BackgroundTasks에서 실행된다.
    """
    token_usage = ChatTokenUsageContext.get()
    
    if not token_usage or not token_usage.token_breakdown:
        return
    
    if not token_usage.message_id:
        return
    
    bus.emit(
        topic=EventTopic.COST,
        event=ChatTokenUsageEvent(
            user_id=user_id,
            workspace_id=workspace_id,
            company_id=company_id,
            message_id=token_usage.message_id,
            token_breakdown=token_usage.token_breakdown,
        )
    )