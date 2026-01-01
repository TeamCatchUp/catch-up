from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    current_query: Optional[str]
    retry_count: int
    datasource: str
    retrieved_docs: list[dict[str, Any]]
    sources: list[dict[str, Any]]
