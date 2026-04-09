from typing import Annotated
from typing import Any
from typing import Literal
from typing import Optional
from typing import TypedDict

from langchain_core.documents import Document
from langgraph.graph.message import add_messages

from catchup.db.models import SourceType
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.structures import GraphDbSearchQuery
from catchup.rag.schemas.structures import VectorDbSearchQuery


def add_tokens(
    a: dict[str, dict[str, int]],
    b: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    """
    토큰 사용량 집계 목적의 reducer.
    """
    if not b:
        return {}
    
    result = dict(a)
    for model, usage in b.items():
        current = result.get(model, {})
        
        # 하위 버전 체크포인트 State 호환을 위해 모든 필드에 .get() 사용
        result[model] = {
            "input_tokens": current.get("input_tokens", 0) + usage.get("input_tokens", 0),
            "output_tokens": current.get("output_tokens", 0) + usage.get("output_tokens", 0),
            "cache_read_tokens": current.get("cache_read_tokens", 0) + usage.get("cache_read_tokens", 0),
            "cache_write_tokens": current.get("cache_write_tokens", 0) + usage.get("cache_write_tokens", 0),
        }
    return result


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
    
    token_breakdown: Annotated[dict[str, dict[str, int]], add_tokens]
    
    rerank_count: int
