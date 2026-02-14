from pydantic import Field
from catchup.chat.schemas import ChatHistoryResponse
from catchup.server.schemas import BasePagination


class ChatHistoryListResponse(BasePagination[ChatHistoryResponse]):
    """채팅 히스토리 응답 (페이지네이션 + 채팅방 메타데이터)"""
    title: str = Field(..., description="채팅방 제목")