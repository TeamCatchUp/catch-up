import logging
import re

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
    context_text, final_sources = _prepare_fixed_context_and_sources(retrieved_docs)
    
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

    full_answer = ""
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

    cited_indices = _extract_citation(full_answer)
    _mark_citations(final_sources, cited_indices)

    logger.info(
        f"LLM이 인용한 문서 인덱스: {cited_indices} / 전체 소스: {len(final_sources)}개"
    )

    return {
        "messages": [AIMessage(content=full_answer)],
        "sources": final_sources
    }


def _prepare_fixed_context_and_sources(
    documents: list[Document],
) -> tuple[str, list[BaseSource]]:
    context_lines = []
    sources = []

    for i, document in enumerate(documents, start=1):
        
        source_dto = BaseSource.from_document(
            index=i,
            doc=document
        )

        if document.metadata.get("db_origin") == "graph":
            line = f"[{i}] [Graph Data] {document.metadata.get('contextual_content', '')}"
            
        else:
            source_type = document.metadata.get("source", "Document")
            line = f"[{i}] (Source: {source_type}\n{document.metadata.get('contextual_content', '')})"

        context_lines.append(line)
        sources.append(source_dto)

    return "\n\n".join(context_lines), sources


def _extract_citation(text: str) -> set[int]:
    matches = re.findall(r"\[(\d+(?:,\s*\d+)*)\]", text)
    indices = set()
    for match in matches:
        for num_str in match.split(","):
            if num_str.strip().isdigit():
                indices.add(int(num_str.strip()))
    return indices


def _mark_citations(sources: list[BaseSource], cited_indices: set[int]) -> None:
    for source in sources:
        if source.index in cited_indices:
            source.is_cited = True
        else:
            source.is_cited = False
