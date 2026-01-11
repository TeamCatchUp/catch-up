import logging
from typing import Annotated, Any, Literal, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph.message import add_messages

from app.rag.models.plan import SearchQuery

logger = logging.getLogger(__name__)


def message_reducer(left: list, right: list):
    all_messages = add_messages(left, right)

    # 전체 메시지 중 사용자에 해당하는 메세지의 인덱스 필터링
    human_message_indices = [
        i for i, m in enumerate(all_messages) if isinstance(m, HumanMessage)
    ]

    # 최근 10 턴의 대화를 short-term memory로 관리
    max_turns = 10
    result = all_messages

    if len(human_message_indices) > max_turns:
        # 최근 max_turns 번째 질문의 위치
        start_index = human_message_indices[-max_turns]

        # 시스템 메시지(프롬프트) 보존
        if isinstance(all_messages[0], SystemMessage):
            result = [all_messages[0]] + all_messages[start_index:]

        else:
            result = all_messages[start_index:]

    return result


class AgentState(TypedDict):
    messages: Annotated[list, message_reducer]  # 대화 내용
    current_query: Optional[str]  # 현재 질문
    retry_count: int  # rewrite 재시도 횟수
    datasource: str  # chitchat vs search_pipline
    search_queries: list[SearchQuery]
    retrieved_docs: list[dict[str, Any]]  # 검색 결과
    sources: list[dict[str, Any]]  # generate_node가 생성하는 최종 출처 데이터
    index_name: list[str]  # 검색 대상 인덱스 이름
    grade_status: Literal["good", "bad", "max_retries"]
