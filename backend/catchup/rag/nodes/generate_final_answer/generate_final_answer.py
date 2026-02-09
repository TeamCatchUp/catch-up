import logging
import re

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.nodes.generate_final_answer.prompt import (
    FALLBACK_ANSWER,
    SYSTEM_ASSISTANT_PROMPT,
)
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
    
    query = state["rewritten_query"]
    forced_query = _build_forced_query(query)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_ASSISTANT_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{query}"),
        ]
    )

    conversation_hiostory = get_conversation_history(state["messages"])
    trimmed_history = trimmer.invoke(conversation_hiostory)

    chain = prompt | llm | StrOutputParser()

    full_answer = ""
    try:
        async with llm_semaphore:
            full_answer = await chain.ainvoke(
                input={
                    "history": trimmed_history,
                    "context": context_text,
                    "query": forced_query,
                    "role": state.get("role", "user"),
                }
            )
            logger.info(f"full_answer: {full_answer}")

    except Exception as e:
        logger.warning(f"Generate final answer failed: {e}")
        return {"messages": [AIMessage(content=FALLBACK_ANSWER)], "sources": []}

    cited_indices = _extract_citation(full_answer)
    _mark_citations(final_sources, cited_indices)

    logger.info(
        f"LLM이 인용한 문서 인덱스: {cited_indices} / 전체 소스: {len(final_sources)}개"
    )

    return {"messages": [AIMessage(content=full_answer)], "sources": final_sources}


def _build_forced_query(query: str) -> str:
    return (
        f"{query}\n\n"
        "---\n"
        "1. **[포맷 엄수]**: 모든 출처는 반드시 **문장 끝 마침표 바로 앞**에 한 칸 띄우고 표기하세요. (예: `...로직입니다 [1].`)\n"
        "2. **[코드 근거]**: 코드 블록을 보여줄 때는, 바로 윗 문장에 반드시 해당 코드의 출처(파일/PR)를 명시해야 합니다.\n"
        "3. **[무관용 원칙]**: [Context]에 근거가 없어 출처 번호를 붙일 수 없는 문장은 절대 작성하지 마세요."
    )


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
            line = f"[{i}] [Graph Data] {document.page_content}"
            
        else:
            source_type = document.metadata.get("source", "Document")
            line = f"[{i}] (Source: {source_type}\n{document.page_content})"

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
