from __future__ import annotations

from typing import Annotated
from typing import Optional
from typing import TypedDict

from langchain_core.documents import Document
from langgraph.graph.message import add_messages

from catchup.automations.structures import GradeResult
from catchup.db.models import SourceType
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.structures import VectorDbSearchQuery


class AutomationState(TypedDict):
    # 트리거 레이어에서 주입
    inquiry_text: str
    user_chat_id: str
    slack_channel_id: str
    slack_credential_id: int
    global_context: GlobalContext

    # rag/ 노드 호환 필드
    messages: Annotated[list, add_messages]
    rewritten_query: str
    vector_search_queries: list[VectorDbSearchQuery]
    retrieved_docs: list[Document]
    tool_filters: Optional[list[SourceType]]
    rerank_count: int

    # automation 전용
    grade_result: Optional[GradeResult]
    guide_text: Optional[str]
