import logging

from fastapi import APIRouter, Depends

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
