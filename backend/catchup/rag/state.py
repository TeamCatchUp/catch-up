from typing import Annotated
from typing import Any
from typing import Literal
from typing import Optional
from typing import TypedDict

from langchain_core.documents import Document
from langgraph.graph.message import add_messages

from catchup.db.models import SourceType
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.prompt_settings import PromptSettings
from catchup.rag.schemas.structures import GraphDbSearchQuery
from catchup.rag.schemas.structures import VectorDbSearchQuery


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: Literal["chitchat", "search_pipeline"]
    
    original_query: str
    rewritten_query: str 
    
    grade_comment: Optional[str] 
    
    vector_search_queries: list[VectorDbSearchQuery]
    graph_search_queries: list[GraphDbSearchQuery]  # Cypher 쿼리 문자열 등
    
    retrieved_docs: list[Document]
    
    grade_status: Literal["good", "bad", "no_relationship", "max_retries"] 
    
    sources: list[dict[str, Any]]  # 최종 출처 목록
    
    retry_count: int  # 최대 2회 제한용
    
    global_context: GlobalContext
    
    tool_filters: Optional[list[SourceType]]
    
    prompt_settings: PromptSettings
    
    rerank_count: int
