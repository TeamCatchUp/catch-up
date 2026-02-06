from typing import Annotated, Any, Literal, TypedDict, Optional

from langgraph.graph.message import add_messages

from catchup.rag.schemas import GraphDbSearchQuery, JiraSource, VectorDbSearchQuery
from catchup.search.schemas import BaseSearchResult


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: Literal["chitchat", "search_pipeline"]
    
    original_query: str
    rewritten_query: str 
    
    grade_comment: Optional[str] 
    
    vector_search_queries: list[VectorDbSearchQuery]
    graph_search_queries: list[GraphDbSearchQuery]  # Cypher 쿼리 문자열 등
    
    retrieved_docs: list[BaseSearchResult]
    
    grade_status: Literal["good", "bad", "no_relationship", "max_retries"] 
    
    sources: list[dict[str, Any]]  # 최종 출처 목록
    related_jira_issues: list[JiraSource]  # 사용자 쿼리와 유사한 Jira Issue 목록
    
    retry_count: int  # 최대 2회 제한용
