import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from catchup.chat.factory import get_chat_service
from catchup.chat.schemas import ChatRequest, ChatResponse
from catchup.chat.engine import ChatService
from catchup.db.dependencies import get_db
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.dependencies import get_rag_global_context

logger = logging.getLogger()

router = APIRouter(prefix="/api/v1")


@router.post("/chat")
async def chat_response(
    request: ChatRequest, service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    return await service.chat(
        query=request.query,
        role=request.role,
        session_id=request.session_id,
    )


@router.post("/chat/stream")
async def chat_response_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    service: ChatService = Depends(get_chat_service),
    global_context: GlobalContext = Depends(get_rag_global_context)
):    
    async def event_generator():
        async for chunk in service.chat_stream(
            db=db,
            query=request.query,
            session_id=request.session_id,
            global_context=global_context
        ):
            yield f"data: {chunk.model_dump_json(ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
#             # ⭐ 위와 동일하게 깔끔하게 전송
#             yield f"data: {chunk.model_dump_json(ensure_ascii=False)}\n\n"

#     return StreamingResponse(event_generator(), media_type="text/event-stream")
