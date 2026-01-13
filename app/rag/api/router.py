import logging
import json
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.rag.dependencies import get_chat_service
from app.rag.models.dto import ChatRequest, ChatResponse
from app.rag.service.chat import ChatService

logger = logging.getLogger()

router = APIRouter()


@router.post("/api/chat")
async def chat_response(
    request: ChatRequest, service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    response = await service.chat(
        query=request.query,
        role=request.role,
        session_id=request.session_id,
        index_list=request.index_list,
    )

    return response


@router.post("/api/chat/stream")
async def chat_response_stream(
    request: ChatRequest, service: ChatService = Depends(get_chat_service)
):
    async def event_generator():        
        async for chunk in service.chat_stream(
            query=request.query,
            role=request.role,
            session_id=request.session_id,
            index_list=request.index_list
        ):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"   
                 
            if chunk["type"] == "result":
                yield "data: [DONE]\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")