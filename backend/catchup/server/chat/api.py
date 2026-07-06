import uuid

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Response
from fastapi import status
from fastapi.responses import StreamingResponse

from catchup.audit.actions import ChatAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.emitters import emit_audit_event
from catchup.audit.metadata import ChatAuditMetadata
from catchup.chat.background_runner import ChatBackgroundRunner
from catchup.chat.background_runner import get_background_runner
from catchup.chat.dependencies import get_prompt_settings
from catchup.chat.dependencies import get_rag_global_context
from catchup.chat.dependencies import get_valid_chat_room
from catchup.chat.engine import ChatService
from catchup.chat.event_store import ChatEventStore
from catchup.chat.event_store import get_event_store
from catchup.chat.factory import get_chat_service
from catchup.chat.schemas import ChatGenerationStatusResponse
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
    description=(
        "스트리밍 기반 채팅 — 새 턴 시작 전용. 이미 실행 중인 턴이 있으면 409를 반환하며, "
        "재연결은 GET /{session_id}/status + GET /{session_id}/stream을 사용한다."
    )
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

    if runner.is_running(session_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 생성 중인 턴이 있습니다. GET /{session_id}/stream으로 재연결하세요.",
        )

    await event_store.clear(str(session_id))

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
        async for event_id, raw_json in event_store.subscribe(str(session_id)):
            yield f"id: {event_id}\ndata: {raw_json}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get(
    path="/{session_id}/status",
    response_model=ChatGenerationStatusResponse,
    description="답변 생성 진행 여부와 재연결 시 배치/실시간 렌더링 경계(cutoff_id)를 반환한다"
)
async def get_chat_generation_status(
    session_id: uuid.UUID,
    response: Response,
    room: ChatRoom = Depends(get_valid_chat_room),
    runner: ChatBackgroundRunner = Depends(get_background_runner),
    event_store: ChatEventStore = Depends(get_event_store),
) -> ChatGenerationStatusResponse:
    response.headers["Cache-Control"] = "no-store"

    if not runner.is_running(session_id):
        return ChatGenerationStatusResponse(is_generating=False, cutoff_id=None)

    cutoff_id, done_seen = await event_store.get_tail_id(str(session_id))
    is_generating = not done_seen

    return ChatGenerationStatusResponse(
        is_generating=is_generating,
        cutoff_id=cutoff_id if is_generating else None,
    )


@router.get(
    path="/{session_id}/stream",
    description=(
        "진행 중이거나 방금 종료된 답변 생성에 재연결해 이벤트를 SSE로 구독한다. "
        "ensure_running을 호출하지 않으며 항상 스트림 처음부터 읽는다."
    )
)
async def chat_response_stream_reconnect(
    session_id: uuid.UUID,
    room: ChatRoom = Depends(get_valid_chat_room),
    event_store: ChatEventStore = Depends(get_event_store),
):
    async def event_generator():
        async for event_id, raw_json in event_store.subscribe(str(session_id)):
            yield f"id: {event_id}\ndata: {raw_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store"},
    )


@router.post(
    path="/{session_id}/cancel",
    description="진행 중인 백그라운드 답변 생성을 취소한다 (그때까지 생성된 내용은 partial로 저장됨)"
)
async def cancel_chat_generation(
    session_id: uuid.UUID,
    room: ChatRoom = Depends(get_valid_chat_room),
    runner: ChatBackgroundRunner = Depends(get_background_runner),
):
    was_running = runner.is_running(session_id)
    await runner.cancel(session_id)

    return {
        "status": "cancelled" if was_running else "not_running",
    }


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
