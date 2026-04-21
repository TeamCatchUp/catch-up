from typing import Annotated
from typing import Literal
from typing import Optional
from typing import TypedDict

from langchain_core.documents import Document
from langgraph.graph.message import add_messages

from catchup.db.models import SourceType
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.prompt_settings import PromptSettings
from catchup.rag.schemas.sources import BaseSource
from catchup.rag.schemas.structures import GapAnalysis
from catchup.rag.schemas.structures import PipelinePlan
from catchup.rag.schemas.structures import SearchStep
from catchup.rag.schemas.structures import VectorDbSearchQuery


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

    original_query: str
    rewritten_query: str

    vector_search_queries: list[VectorDbSearchQuery]

    retrieved_docs: list[Document]

    sources: list[BaseSource]  # 최종 출처 목록

    global_context: GlobalContext

    tool_filters: Optional[list[SourceType]]

    prompt_settings: PromptSettings

    rerank_count: int

    max_pipeline_type: Literal["simple", "standard", "complex"]

    # Agentic RAG
    pipeline_plan: PipelinePlan | None  # Supervisor 출력. None이면 legacy 경로 fallback

    agent_iteration: int  # ReAct 루프 현재 반복 수

    accumulated_docs: list[Document]  # ReAct 반복 간 누적 문서 (search_tool_executor_node에서 직접 dedup)

    search_plan: list[SearchStep] | None  # complex planner 출력

    gap_analysis: GapAnalysis | None  # complex gap_analysis_node 출력

    turn_number: int  # supervisor가 매 턴 시작 시 +1. engine.py에서 초기화 안 함 (체크포인터 유지)

    doc_cache: list[Document]  # 세션 내 누적 문서 캐시. dedup + window cap 100. 검색 파이프라인이 rerank 후 병합

    agent_reasoning: str | None  # 에이전트의 최종 추론 결과 (최종 답변 노드에 전달용)
