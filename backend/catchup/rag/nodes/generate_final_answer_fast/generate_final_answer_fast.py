import structlog
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import build_system_message
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import log_node
from catchup.rag.nodes.utils import mark_citations
from catchup.rag.nodes.utils import parse_citations
from catchup.rag.nodes.utils import prepare_retrieved_context_text
from catchup.rag.policies import CITATION_POLICY_MESSAGE
from catchup.rag.policies import FALLBACK_ANSWER
from catchup.rag.schemas.prompt_settings import PromptSettings
from catchup.rag.schemas.sources import BaseSource
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def generate_final_answer_fast_node(state: AgentState, llm: BaseChatModel):

    # 토큰 사용량 초기화
    token_usages = {"token_breakdown": {}}

    # Context 가공
    retrieved_docs: list[Document] = state.get("retrieved_docs", [])
    if not retrieved_docs:
        logger.warning("no_documents_retrieved", action="fallback_answer_generated")
        return {
            "messages": [AIMessage(content=FALLBACK_ANSWER)],
            "sources": [],
        }
    retrieved_context = prepare_retrieved_context_text(retrieved_docs)
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
    if agent_reasoning:
        agent_research_prompt = prompt_loader.get_prompt(
            "rag/agent_research_summary",
            agent_reasoning=agent_reasoning,
        )
        dynamic_prompts.append(agent_research_prompt)

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
            llm=llm, messages=messages, semaphore=rag_semaphores.llm_large
        )
        full_answer = raw_response.content

        logger.debug(
            "fast_answer_generated",
            original_query=state.get("original_query"),
            rewritten_query=state.get("rewritten_query"),
            full_answer=full_answer,
        )

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

    candidate_sources = [
        BaseSource.from_document(
            index=i,
            doc=document,
        )
        for i, document in enumerate(retrieved_docs, start=1)
    ]
    final_sources = mark_citations(candidate_sources, citations)

    sorted_indices = sorted(citations.keys(), key=int)
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
