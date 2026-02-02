import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.observability.langfuse_client import langfuse_handler
from catchup.rag.nodes.generate.prompt import SYSTEM_ASSISTANT_PROMPT
from catchup.rag.nodes.utils import get_latest_query, llm_semaphore
from catchup.rag.schemas import BaseSource
from catchup.rag.state import AgentState
from catchup.search.schemas import BaseSearchResult

logger = logging.getLogger(__name__)


async def generate_node(state: AgentState):
    logger.info("generate node 진입")
    llm_service = get_llm_service()
    llm = llm_service.get_llm()
    trimmer = llm_service.get_trimmer()

    messages = state["messages"]
    current_query = get_latest_query(messages)

    forced_query = (
        f"{current_query}\n\n"
        "---\n"
        "1. **[포맷 엄수]**: 모든 출처는 반드시 **문장 끝 마침표 바로 앞**에 한 칸 띄우고 표기하세요. (예: `...로직입니다 [1].`)\n"
        "2. **[코드 근거]**: 코드 블록을 보여줄 때는, 바로 윗 문장에 반드시 해당 코드의 출처(파일/PR)를 명시해야 합니다.\n"
        "3. **[무관용 원칙]**: [Context]에 근거가 없어 출처 번호를 붙일 수 없는 문장은 절대 작성하지 마세요."
    )

    # agent state로부터 검색 결과 획득
    retrieved_docs: list[BaseSearchResult] = state.get("retrieved_docs", [])

    # 문서 전처리 (Context 텍스트 생성 및 Source 객체 초기화)
    context_text, processed_sources = _preprocess_documents(retrieved_docs)

    # 프롬프트 생성
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_ASSISTANT_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{query}"),
        ]
    )

    # 체인
    chain = prompt | llm | StrOutputParser()

    # 사용자-어시스턴트 대화 필터링
    conversation_messages = [
        m for m in messages if isinstance(m, (HumanMessage, AIMessage))
    ]

    # 마지막 대화를 제외한 모든 사용자-어시스턴트 대화 내용
    history_messages = conversation_messages[:-1]

    # 대화 히스토리 trim
    trimmed_history = trimmer.invoke(history_messages)

    # LLM 호출
    async with llm_semaphore:
        answer = await chain.ainvoke(
            input={
                "history": trimmed_history,
                "context": context_text,
                "query": forced_query,
                "role": state.get("role", "user"),
            },
            config={"callbacks": [langfuse_handler]},
        )

    # LLM이 답변에 사용한 Document의 인덱스 파싱
    cited_indices = extract_citation(answer)
    logger.info(f"LLM이 인용한 문서 인덱스: {cited_indices}")

    # 사용자에게 제공할 최종 source 정제.
    final_sources = _select_final_sources(
        processed_sources=processed_sources,
        cited_indices=cited_indices,
        target_k=8,
        sanity_threshold=settings.FINAL_SOURCES_SANITY_THRESHOLD,
    )

    return {"messages": [AIMessage(content=answer)], "sources": final_sources}


def _preprocess_documents(
    retrieved_docs: list[BaseSearchResult],
) -> tuple[str, list[dict[str, Any]]]:
    """
    검색 결과를 LLM용 Context Text와 Frontend용 Source 객체로 변환
    """
    # context_text 생성을 위한 임시 리스트
    context_text_list = []

    # 사용자 제공용 Source 리스트
    processed_sources = []

    for i, doc in enumerate(retrieved_docs, start=1):
        formatted_text = doc.to_context_text(index=i)
        context_text_list.append(formatted_text)

        source_dto = BaseSource.from_search_result(index=i, doc=doc)
        processed_sources.append(source_dto)

    # LLM 제공용 context 연결
    full_context_text = "\n\n".join(context_text_list)

    return full_context_text, processed_sources


def _select_final_sources(
    processed_sources: list[BaseSource],
    cited_indices: set[int],
    target_k: int = 5,
    sanity_threshold: float = 0.01,
) -> list[BaseSource]:
    """
    인용 여부, Threshold, Fallback 로직을 통해 최종 Source 리스트 선정 및 정렬
    """
    final_sources: list[BaseSource] = []
    seen_indices = set()

    # LLM이 인용한 document가 존재하는 경우
    if cited_indices:
        for cited_num in cited_indices:
            idx = cited_num - 1  # 1-based -> 0-based 변환
            if 0 <= idx < len(processed_sources):
                if idx not in seen_indices:
                    processed_sources[idx].is_cited = True
                    final_sources.append(processed_sources[idx])
                    seen_indices.add(idx)

        logger.info(f"LLM이 인용한 문서: {len(final_sources)}개")

    # 점수 내림차순 정렬 (객체 자체 정렬)
    sorted_candidates = sorted(
        processed_sources, key=lambda x: x.relevance_score, reverse=True
    )

    for doc in sorted_candidates:
        if len(final_sources) >= target_k:
            break

        idx = doc.index - 1
        if idx in seen_indices:
            continue

        if (doc.relevance_score or 0.0) < sanity_threshold:
            continue

        final_sources.append(doc)
        seen_indices.add(idx)

    logger.info(f"최종 선별된 문서 수: {len(final_sources)}개 (Target K: {target_k})")

    # 1순위: 인용 여부
    # 2순위: Relevance Score 기준 내림차순
    final_sources.sort(key=lambda x: (not x.is_cited, x.index))

    return final_sources


def extract_citation(text: str) -> set[int]:
    matches = re.findall(r"\[(\d+(?:,\s*\d+)*)\]", text)

    indices = set()
    for match in matches:
        for num_str in match.split(","):
            if num_str.strip().isdigit():
                indices.add(int(num_str.strip()))

    return indices
