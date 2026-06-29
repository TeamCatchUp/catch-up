import uuid

from fastapi import APIRouter
from fastapi import Depends
from fastapi.responses import StreamingResponse

from catchup.audit.actions import ChatAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.emitters import emit_audit_event
from catchup.audit.metadata import ChatAuditMetadata
from catchup.chat.dependencies import get_prompt_settings
from catchup.chat.dependencies import get_rag_global_context
from catchup.chat.background_runner import ChatBackgroundRunner
from catchup.chat.background_runner import get_background_runner
from catchup.chat.dependencies import get_valid_chat_room
from catchup.chat.engine import ChatService
from catchup.chat.event_store import ChatEventStore
from catchup.chat.event_store import get_event_store
from catchup.chat.factory import get_chat_service
from catchup.chat.schemas import ChatRequest
from catchup.chat.schemas import ChatResponse
from catchup.db.models import ChatRoom
from catchup.schemas.context import GlobalContext
from catchup.schemas.prompt_settings import PromptSettings

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["RAG Chat Service"]
)


@router.post(
    path="",
    description="일반 채팅 (스트리밍 지원 X)",
    deprecated=True
)
async def chat_response(
    request: ChatRequest, service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    return await service.chat(
        query=request.query,
        role=request.role,
        session_id=request.session_id,
    )


@router.post(
    path="/stream",
    description="스트리밍 기반 채팅 — 페이지 이탈 후 재연결 시 처음부터 replay됨"
)
async def chat_response_stream(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
    global_context: GlobalContext = Depends(get_rag_global_context),
    prompt_settings: PromptSettings = Depends(get_prompt_settings),
    runner: ChatBackgroundRunner = Depends(get_background_runner),
    event_store: ChatEventStore = Depends(get_event_store),
):
    session_id = request.session_id
    query = request.query
    tool_filters = request.tool_filters
    mode = request.mode

    emit_audit_event(
        action=ChatAction.SEND_QUERY,
        status=AuditStatus.SUCCESS,
        level=AuditLevel.INFO,
        metadata=ChatAuditMetadata(
            session_id=session_id,
            query=query,
            tool_filters=tool_filters
        ),
    )

    await runner.ensure_running(
        session_id,
        coro_factory=lambda: service.run_background(
            global_context=global_context,
            prompt_settings=prompt_settings,
            session_id=session_id,
            event_store=event_store,
            tool_filters=tool_filters,
            query=query,
            mode=mode,
        ),
    )

    async def event_generator():
        async for raw_json in event_store.subscribe(str(session_id)):
            yield f"data: {raw_json}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post(
    path="/{session_id}/reset-last",
    description="가장 마지막 대화 턴(사용자 질문 + 답변)을 삭제하고, 삭제된 사용자 질문 반환"
)
async def reset_last_conversation_turn(
    session_id: uuid.UUID,
    room: ChatRoom = Depends(get_valid_chat_room),
    chat_service: ChatService = Depends()
):
    deleted_query = await chat_service.reset_last_turn(
        room_id=room.id,
        session_id=session_id
    )

    if not deleted_query:
        return {
            "status": "no_content",
            "message": "삭제할 대화가 없습니다."
        }

    return {
        "status": "success",
        "restored_query": deleted_query
    }
