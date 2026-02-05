import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from catchup.chat.factory import get_chat_service
from catchup.chat.schemas import ChatRequest, ChatResponse, ChatStreamingResumeRequest
from catchup.chat.service import ChatService

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
        index_list=request.index_list,
    )


@router.post("/api/chat/stream")
async def chat_response_stream(
    request: ChatRequest, service: ChatService = Depends(get_chat_service)
):
    async def event_generator():
        async for chunk in service.chat_stream(
            query=request.query,
            role=request.role,
            session_id=request.session_id,
            index_list=request.index_list,
        ):
            yield f"data: {chunk.model_dump_json(ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/api/chat/stream/resume")
async def chat_resume(
    request: ChatStreamingResumeRequest,
    service: ChatService = Depends(get_chat_service),
):
    async def event_generator():
        async for chunk in service.chat_stream(
            session_id=request.session_id,
            resume_data=request.user_selected_pull_requests,
        ):
            # ⭐ 위와 동일하게 깔끔하게 전송
            yield f"data: {chunk.model_dump_json(ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
