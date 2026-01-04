from typing import Annotated, Any, Optional, TypedDict, Literal

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages] # 대화 내용
    current_query: Optional[str] # 현재 질문
    retry_count: int # rewrite 재시도 횟수
    datasource: str # chitchat vs retrieval
    retrieved_docs: list[dict[str, Any]] # 검색 결과
    sources: list[dict[str, Any]] # generate_node가 생성하는 최종 출처 데이터
    index_name: str # 검색 대상 인덱스 이름
    grade_status: Literal["good", "bad", "max_retries"]
