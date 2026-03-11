from importlib import metadata
import logging
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from catchup.audit.enums import AuditLevel
from catchup.audit.metadata import ChatAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.chat.dependencies import get_valid_chat_room
from catchup.chat.factory import get_chat_service
from catchup.chat.schemas import ChatRequest, ChatResponse
from catchup.chat.engine import ChatService
from catchup.db.dependencies import get_db
from catchup.db.models import ChatRoom
from catchup.events.enums import ChatEventAction, EventType
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.dependencies import get_rag_global_context

logger = logging.getLogger()

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
    description="스트리밍 기반 채팅"
)
async def chat_response_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    service: ChatService = Depends(get_chat_service),
    global_context: GlobalContext = Depends(get_rag_global_context)
):    
    session_id = request.session_id
    query = request.query
    tool_filters = request.tool_filters
    
    emit_audit_event(
        event_type=EventType.CHAT,
        event_action=ChatEventAction.MESSAGE_RECEIVED,
        level=AuditLevel.INFO,
        metadata=ChatAuditMetadata(
            session_id=session_id,
            query=query,
            tool_filters=tool_filters
        ),
        immediate=True
    )
    
    async def event_generator():
        async for chunk in service.chat_stream(
            db=db,
            query=query,
            session_id=session_id,
            tool_filters=tool_filters,
            global_context=global_context
        ):
            yield f"data: {chunk.model_dump_json(ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post(
    path="/{session_id}/reset-last",
    description="가장 마지막 대화 턴(사용자 질문 + 답변)을 삭제하고, 삭제된 사용자 질문 반환"
)
async def reset_last_conversation_turn(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    room: ChatRoom = Depends(get_valid_chat_room),
    chat_service: ChatService = Depends()
):
    deleted_query = await chat_service.reset_last_turn(
        db=db,
        room=room
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

# @router.post("/api/chat/stream/resume")
# async def chat_resume(
#     request: ChatStreamingResumeRequest,
#     service: ChatService = Depends(get_chat_service),
# ):
#     async def event_generator():
#         async for chunk in service.chat_stream(
#             session_id=request.session_id,
#             resume_data=request.user_selected_pull_requests,
#         ):
#             # 위와 동일하게 깔끔하게 전송
#             yield f"data: {chunk.model_dump_json(ensure_ascii=False)}\n\n"

#     return StreamingResponse(event_generator(), media_type="text/event-stream")
