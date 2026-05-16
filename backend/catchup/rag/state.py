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
from catchup.rag.schemas.structures import PipelinePlan
from catchup.rag.schemas.structures import SearchStep
from catchup.rag.schemas.structures import SearchTurnMeta
from catchup.rag.schemas.structures import VectorDbSearchQuery


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

    original_query: str
    
    rewritten_query: str

    vector_search_queries: list[VectorDbSearchQuery]

    retrieved_docs: list[Document]

    # 최종 출처 목록
    sources: list[BaseSource]

    global_context: GlobalContext

    tool_filters: Optional[list[SourceType]]

    prompt_settings: PromptSettings

    rerank_count: int

    max_pipeline_type: Literal["simple", "standard", "complex"]
    
    # Supervisor 출력. None이면 legacy 경로 fallback
    pipeline_plan: PipelinePlan | None

    agent_iteration: int  # ReAct 루프 현재 반복 수

    # ReAct 반복 간 누적 문서 (search_tool_executor_node에서 직접 dedup)
    accumulated_docs: list[Document]

    # 에이전트가 ToolMessage로 실제 본 문서 ID 목록.
    # 매 검색 턴마다 신규 문서만 미리보기로 노출하기 위한 추적용.
    # accumulated_docs와 달리 "에이전트 인지" 기준이라 분리 관리.
    agent_seen_doc_ids: list[str]

    search_plan: list[SearchStep] | None  # complex planner 출력

    # supervisor가 매 턴 시작 시 +1.
    # engine.py에서 초기화 안 함 (체크포인터 유지)
    turn_number: int  

    # 직전 검색 턴(simple/standard/complex)의 rerank 결과. hot cache.
    # 검색 턴마다 overwrite. reuse 턴에서는 갱신 안 됨.
    doc_cache: list[Document]

    # 모든 검색 턴(simple/standard/complex)의 경량 메타데이터 누적.
    # doc_ids만 저장 (full Document 미보관). reuse 시 필요한 과거 턴 docs를 DB에서 lazy fetch.
    # 리스트 내 순서(1-based)가 supervisor에게 노출되는 검색 턴 ID 역할.
    search_turn_history: list[SearchTurnMeta]

    # 에이전트의 최종 추론 결과 (최종 답변 노드에 전달용)
    agent_reasoning: str | None

    # 에이전트가 핵심이라고 판단한 문서 ID 목록 (Boosting용)
    essential_doc_ids: list[str]

    # 에이전트 지목 ∩ rerank top_k 통과 문서 ID 목록.
    # 에이전트와 reranker 양쪽이 인정한 신뢰도 높은 문서.
    # 답변 노드가 인덱스로 변환해 LLM에게 우선순위 신호로 전달.
    confirmed_essential_doc_ids: list[str]

    # 리랭킹 결과 및 부스팅 이력 (Langfuse 로깅용)
    rerank_metadata: dict | None
    
    # supervisor가 추출한 질문 주제 (3~5단어 한국어 명사구)
    query_topic: str | None
    
    # Slack 스레드 맥락 (턴마다 갱신, 비Slack 요청은 None)
    slack_thread_context: str | None
