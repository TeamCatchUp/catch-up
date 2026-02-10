import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from catchup.auth.dependencies import get_current_user
from catchup.chat.factory import get_chat_service
from catchup.chat.schemas import ChatRequest, ChatResponse
from catchup.chat.service import ChatService
from catchup.db.models import User
from catchup.rag.schemas.context import GlobalContext, GlobalUserContext
from catchup.server.chat.context import get_full_global_context

logger = logging.getLogger()

router = APIRouter()


@router.post("/api/chat")
async def chat_response(
    request: ChatRequest, service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    return await service.chat(
        query=request.query,
        role=request.role,
        session_id=request.session_id,
    )


@router.post("/api/chat/stream")
async def chat_response_stream(
    request: ChatRequest, 
    service: ChatService = Depends(get_chat_service),
    global_context: GlobalContext = Depends(get_full_global_context)
):    
    async def event_generator():
        async for chunk in service.chat_stream(
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
