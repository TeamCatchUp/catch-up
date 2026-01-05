from fastapi import APIRouter, Depends
import logging

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
        index_name=request.index_name
    )
    
    logger.info(f"타겟 인덱스:{request.index_name}")
    logger.info(f"\n질문: {request.query}\n답변: {response.answer}")
    
    return response
