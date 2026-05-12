import structlog
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import build_confirmed_priority_prompt
from catchup.rag.nodes.utils import build_doc_groups
from catchup.rag.nodes.utils import build_system_message
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import log_node
from catchup.rag.nodes.utils import mark_citations
from catchup.rag.nodes.utils import parse_citations
from catchup.rag.nodes.utils import render_grouped_context_text
from catchup.rag.nodes.utils import sanitize_agent_reasoning
from catchup.rag.nodes.utils import scrub_orphan_indices
from catchup.rag.policies import CITATION_POLICY_MESSAGE
from catchup.rag.policies import FALLBACK_ANSWER
from catchup.rag.policies import NO_DOCUMENTS_ANSWER
from catchup.rag.retryable import RETRYABLE_ERRORS
from catchup.rag.schemas.prompt_settings import PromptSettings
from catchup.rag.schemas.sources import SOURCE_METADATA
from catchup.rag.schemas.sources import BaseSource
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def generate_final_answer_fast_node(
    state: AgentState,
    llm: BaseChatModel,
):

    # 토큰 사용량 초기화
    token_usages = {"token_breakdown": {}}

    # Context 가공
    retrieved_docs: list[Document] = state.get("retrieved_docs", [])
    if not retrieved_docs:
        logger.warning("no_documents_retrieved", action="fallback_answer_generated")
        return {
            "messages": [AIMessage(content=NO_DOCUMENTS_ANSWER)],
            "sources": [],
        }
    # 같은 문서에서 나온 청크들은 한 인덱스 아래로 묶어 사용자 관점의 출처 중복을 막는다.
    doc_groups = build_doc_groups(retrieved_docs)
    retrieved_context = render_grouped_context_text(doc_groups)
    global_context = state["global_context"].model_dump()

    # 사용자 질문
    query = state["rewritten_query"]
    query_with_citation_policy = query + CITATION_POLICY_MESSAGE

    # 시스템 프롬프트 빌드
    prompt_settings: PromptSettings = state.get("prompt_settings")
    agent_reasoning = state.get("agent_reasoning")

    prompts = _load_prompts(
        global_context=global_context,
        retrieved_context=retrieved_context,
        prompt_settings=prompt_settings,
    )

    dynamic_prompts = [
        prompts["global_context"],
        prompts["retrieved_context"],
        prompts["settings"],
    ]

    # 에이전트의 중간 추론 결과가 있다면 별도의 동적 프롬프트 블록으로 추가한다.
    # 단, <key_document_indices>는 rerank 후 stale하므로 제거 — 정확한 인덱스는
    # confirmed_priority_documents 블록으로 별도 전달.
    if agent_reasoning:
        sanitized_reasoning = sanitize_agent_reasoning(agent_reasoning)
        if sanitized_reasoning:
            agent_research_prompt = prompt_loader.get_prompt(
                "rag/agent_research_summary",
                agent_reasoning=sanitized_reasoning,
            )
            dynamic_prompts.append(agent_research_prompt)

    # 에이전트 지목 ∩ reranker top_k 교집합 문서를 1-base 인덱스로 LLM에게 전달.
    confirmed_prompt = build_confirmed_priority_prompt(
        groups=doc_groups,
        confirmed_essential_doc_ids=state.get("confirmed_essential_doc_ids"),
    )
    if confirmed_prompt:
        dynamic_prompts.append(confirmed_prompt)

    system_message = build_system_message(
        static_prompt=prompts["system"],
        dynamic_prompts=dynamic_prompts,
        cache_prompt=False,
    )

    # 대화 내역 복원
    conversation_history = get_conversation_history(state["messages"])

    # 메세지 구성
    messages = (
        [system_message]
        + conversation_history
        + [HumanMessage(content=query_with_citation_policy)]
    )

    # LLM 호출
    try:
        raw_response, token_usages = await ainvoke_llm_with_token_usage(
            llm=llm,
            messages=messages,
            semaphore=rag_semaphores.llm_large,
        )
        full_answer = raw_response.content

        logger.debug(
            "fast_answer_generated",
            original_query=state.get("original_query"),
            rewritten_query=state.get("rewritten_query"),
            full_answer=full_answer,
        )

    except RETRYABLE_ERRORS:
        raise
    except Exception as e:
        logger.warning(
            "fast_answer_generation_node_failed",
            action="fallback_answer_generated",
            error=str(e),
            exc_info=True,
        )
        return {
            "messages": [AIMessage(content=FALLBACK_ANSWER)],
            "sources": [],
        }

    # 최종 답변 및 인용 대상 추출
    answer_body, citations = parse_citations(full_answer)

    # 환각 방어: 본문에 박힌 out-of-range [N]은 표시 인덱스에 매칭되지 않으므로 제거.
    valid_indices = {g.display_index for g in doc_groups}
    answer_body = scrub_orphan_indices(answer_body, valid_indices)

    # 그룹 단위로 BaseSource를 만들어, 한 문서를 가리키는 여러 청크가 사용자에게는
    # 한 출처로 보이도록 한다. 대표 청크의 메타데이터를 사용한다.
    candidate_sources = [
        BaseSource.from_document(
            index=group.display_index,
            doc=group.representative,
        )
        for group in doc_groups
    ]
    final_sources = mark_citations(candidate_sources, citations)

    sorted_indices = sorted(citations, key=int)
    logger.debug(
        "llm_cited_sources",
        cited_indices=sorted_indices,
        total_sources=len(final_sources),
    )

    return {
        "messages": [AIMessage(content=answer_body)],
        "sources": final_sources,
        **token_usages,
    }


def _load_prompts(
    global_context: dict,
    retrieved_context: str,
    prompt_settings: PromptSettings,
) -> dict:
    return {
        "system": prompt_loader.get_prompt(
            "rag/generate_final_answer_fast",
            prompt_settings=prompt_settings,
            sources=list(SOURCE_METADATA.values()),
        ),
        "global_context": prompt_loader.get_prompt(
            "common/global_context",
            **global_context,
        ),
        "retrieved_context": prompt_loader.get_prompt(
            "common/retrieved_context",
            context=retrieved_context,
        ),
        "settings": prompt_loader.get_prompt(
            "settings/settings",
            prompt_settings=prompt_settings,
        ),
    }
