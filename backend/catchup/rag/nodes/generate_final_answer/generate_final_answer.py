import json
import logging
import re
from re import DOTALL

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.constants import FALLBACK_ANSWER
from catchup.rag.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import get_conversation_history, llm_semaphore, log_node
from catchup.rag.schemas.sources import BaseSource
from catchup.rag.state import AgentState


logger = logging.getLogger(__name__)

@log_node
async def generate_final_answer_node(state: AgentState):
    llm_service = get_llm_service(LlmProvider.OPENAI)
    llm = llm_service.get_llm()
    trimmer = llm_service.get_trimmer()

    retrieved_docs: list[Document] = state.get("retrieved_docs", [])
    
    if not retrieved_docs:
        logger.warning("검색된 문서가 없음 -> Fallback 답변 반환")
        return {
            "messages": [AIMessage(content=FALLBACK_ANSWER)],
            "sources": []
        }
    
    context_text = _prepare_context_text(retrieved_docs)
    
    global_context = state["global_context"].model_dump()
    query = state["rewritten_query"]

    prompt = prompt_loader.get_prompt(
        "generate_final_answer",
        context=context_text,
        **global_context
    )

    conversation_history = get_conversation_history(state["messages"])
    trimmed_history = trimmer.invoke(conversation_history)
    
    messages = [SystemMessage(content=prompt)] + trimmed_history + [HumanMessage(content=query)]

    chain = llm | StrOutputParser()

    try:
        async with llm_semaphore:
            full_answer = await chain.ainvoke(input=messages)
            logger.info(f"full_answer: {full_answer}")

    except Exception as e:
        logger.warning(f"Generate final answer failed: {e}")
        return {
            "messages": [AIMessage(content=FALLBACK_ANSWER)],
            "sources": []
        }
    
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
    logger.info(
        f"LLM이 인용한 문서 인덱스: {sorted_indices} / 전체 소스: {len(final_sources)}개"
    )

    return {
        "messages": [AIMessage(content=answer_body)],
        "sources": final_sources
    }


def _prepare_context_text(documents: list[Document]) -> str:
    context_lines = []
    
    for i, document in enumerate(documents, start=1):
        if document.metadata.get("db_origin") == "graph":
            line = f"[{i}] [Graph Data] {document.metadata.get('contextual_content', '')}"
            
        else:
            source_type = document.metadata.get("source", "Document")
            line = f"[{i}] (Source: {source_type}\n{document.metadata.get('contextual_content', '')})"

        context_lines.append(line)
        
    return "\n\n".join(context_lines)


def _parse_citation(full_answer: str) -> tuple[str, dict[str, str]]:
    body_part = full_answer
    citation_dict = {}
    
    match = re.search(r"<citations>(.*?)</citations>", full_answer, DOTALL)
    if match:
        body_part = full_answer[:match.start()].strip()
        try:
            citation_dict = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            logger.warning("Citations JSON parsing failed.")
    
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