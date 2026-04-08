import json
import re
from re import DOTALL

import structlog
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from catchup.costs.utils import extract_token_usages
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import build_system_message_with_prompt_caching
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import log_node
from catchup.rag.nodes.utils import prepare_retrieved_context_text
from catchup.rag.policies import CITATION_POLICY_MESSAGE
from catchup.rag.policies import FALLBACK_ANSWER
from catchup.rag.schemas.sources import BaseSource
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()

@log_node
async def generate_final_answer_node(state: AgentState, llm: BaseChatModel):

    # 토큰 사용량 초기화
    token_usages = {"token_breakdown": {}}
    
    # Context 가공
    retrieved_docs: list[Document] = state.get("retrieved_docs", [])
    if not retrieved_docs:
        logger.warning("no_documents_retrieved", action="fallback_answer_generated")
        return {
            "messages": [AIMessage(content=FALLBACK_ANSWER)],
            "sources": [],
            **token_usages
        }
    retrieved_context = prepare_retrieved_context_text(retrieved_docs)
    global_context = state["global_context"].model_dump()
    
    # 사용자 질문
    query = state["rewritten_query"]
    query_with_citation_policy = query + CITATION_POLICY_MESSAGE

    # 시스템 프롬프트 빌드
    prompts = _load_prompts(global_context, retrieved_context)
    system_message = build_system_message_with_prompt_caching(
        static_prompt=prompts["system"],
        dynamic_prompts=[
            prompts["global_context"],
            prompts["retrieved_context"]
        ]
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
        async with rag_semaphores.final_answer:
            raw_response = await llm.ainvoke(input=messages)
            token_usages = extract_token_usages(raw_response)
            full_answer = raw_response.content
            
            logger.debug(
                "final_answer_generated",
                original_query=state.get("original_query"),
                rewritten_query=state.get("rewritten_query"),
                full_answer=full_answer
            )

    except Exception as e:
        logger.warning(
            "final_answer_generation_node_failed",
            action="fallback_answer_generated",
            error=str(e),
            exc_info=True,
        )
        return {
            "messages": [AIMessage(content=FALLBACK_ANSWER)],
            "sources": [],
            **token_usages,
        }
    
    # 최종 답변 및 인용 대상 추출
    answer_body, citations = _parse_citation(full_answer)
    
    candidate_sources = [
        BaseSource.from_document(
            index=i,
            doc=document
        ) 
        for i, document in enumerate(retrieved_docs, start=1)
    ]
    final_sources = _mark_citations(candidate_sources, citations)

    sorted_indices = sorted(citations.keys(), key=int)
    logger.debug(
        "llm_cited_sources", 
        cited_indices=sorted_indices,
        total_sources=len(final_sources)
    )

    return {
        "messages": [AIMessage(content=answer_body)],
        "sources": final_sources,
        **token_usages,
    }


def _load_prompts(
    global_context: dict,
    retrieved_context: str,
) -> dict:
    return {
        "system": prompt_loader.get_prompt("rag/generate_final_answer"),
        "global_context": prompt_loader.get_prompt(
            "common/global_context", 
            **global_context
        ),
        "retrieved_context": prompt_loader.get_prompt(
            "common/retrieved_context",
            context=retrieved_context
        ),
    }


def _parse_citation(full_answer: str) -> tuple[str, dict[str, str]]:
    body_part = full_answer
    citation_dict = {}
    
    # 정상 동작: 태그가 완전히 닫힘. (<citations>...</citations>)
    match = re.search(r"<citations>(.*?)</citations>", full_answer, DOTALL)
    if match:
        body_part = full_answer[:match.start()].strip()
        try:
            citation_dict = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            logger.warning("citations_parsing_failed")
    
    # 비정상 동작 태그가 열리거나 불완전함. (<citations>...)
    elif open_tag_match := re.search(r"<citations>", full_answer):
        logger.warning(
            "citations_block_truncated",
            context="token_overflow"
        )
        body_part = full_answer[:open_tag_match.start()].strip() # 
        if not body_part:
            body_part = FALLBACK_ANSWER
    
    return body_part, citation_dict


def _mark_citations(
    candidate_sources: list[BaseSource],
    citations: dict[str, str]
) -> list[BaseSource]:
    
    final_sources = []
    
    for source in candidate_sources:
        idx = str(source.index)  # JSON Key -> str
        if idx in citations:
            source.is_cited = True
            source.citation_rationale = citations[idx]
        else:
            source.is_cited = False

        final_sources.append(source)
    
    return final_sources