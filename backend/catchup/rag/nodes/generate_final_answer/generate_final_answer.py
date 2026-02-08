import logging
import re

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.observability.langfuse_client import langfuse_handler
from catchup.rag.nodes.chitchat.chitchat import FALLBACK_ANSWER
from catchup.rag.nodes.generate_final_answer.prompt import SYSTEM_ASSISTANT_PROMPT
from catchup.rag.nodes.utils import get_conversation_history, llm_semaphore, log_node
from catchup.rag.schemas import BaseSource
from catchup.rag.state import AgentState


logger = logging.getLogger(__name__)

FALLBACK_ANSWER = "답변을 생성하지 못했습니다. 다시 시도해주세요."

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

    try:
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
    except Exception as e:
        logger.warning(f"Generate final answer failed: {e}")
        return {
            "messages": [AIMessage(content=FALLBACK_ANSWER)],
            "sources": []
        }

    cited_indices = _extract_citation(answer)
    # _mark_citations(final_sources, cited_indices)
    
    logger.info(f"LLM이 인용한 문서 인덱스: {cited_indices} / 전체 소스: {len(final_sources)}개")


    return {"messages": [AIMessage(content=answer)], "sources": final_sources}


def _build_forced_query(query: str) -> str:
    return (
        f"{query}\n\n"
        "---\n"
        "1. **[포맷 엄수]**: 모든 출처는 반드시 **문장 끝 마침표 바로 앞**에 한 칸 띄우고 표기하세요. (예: `...로직입니다 [1].`)\n"
        "2. **[코드 근거]**: 코드 블록을 보여줄 때는, 바로 윗 문장에 반드시 해당 코드의 출처(파일/PR)를 명시해야 합니다.\n"
        "3. **[무관용 원칙]**: [Context]에 근거가 없어 출처 번호를 붙일 수 없는 문장은 절대 작성하지 마세요."
    )


def _prepare_fixed_context_and_sources(
    documents: list[Document]
) -> tuple[str, list[BaseSource]]:
    context_lines = []
    sources = []
    
    for i, document in enumerate(documents, start=1):
        try:
            # source_dto = BaseSource.from_search_result(index=i, doc=document)
            source_dto = None
        except AttributeError:
            raise
        
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


def _mark_citations(
    sources: list[BaseSource],
    cited_indices: set[int]
) -> None:
    for source in sources:
        if source.index in cited_indices:
            source.is_cited = True
        else:
            source.is_cited = False


# def _preprocess_documents(
#     retrieved_docs: list[BaseSearchResult],
# ) -> tuple[str, list[dict[str, Any]]]:
#     """
#     검색 결과를 LLM용 Context Text와 Frontend용 Source 객체로 변환
#     """
#     # context_text 생성을 위한 임시 리스트
#     context_text_list = []

#     # 사용자 제공용 Source 리스트
#     processed_sources = []

#     for i, doc in enumerate(retrieved_docs, start=1):
#         formatted_text = doc.to_context_text(index=i)
#         context_text_list.append(formatted_text)

#         source_dto = BaseSource.from_search_result(index=i, doc=doc)
#         processed_sources.append(source_dto)

#     # LLM 제공용 context 연결
#     full_context_text = "\n\n".join(context_text_list)

#     return full_context_text, processed_sources

# def _select_final_sources(
#     processed_sources: list[BaseSource],
#     cited_indices: set[int],
#     target_k: int = 5,
#     sanity_threshold: float = 0.01,
# ) -> list[BaseSource]:
#     """
#     인용 여부, Threshold, Fallback 로직을 통해 최종 Source 리스트 선정 및 정렬
#     """
#     final_sources: list[BaseSource] = []
#     seen_indices = set()

#     # LLM이 인용한 document가 존재하는 경우
#     if cited_indices:
#         for cited_num in cited_indices:
#             idx = cited_num - 1  # 1-based -> 0-based 변환
#             if 0 <= idx < len(processed_sources):
#                 if idx not in seen_indices:
#                     processed_sources[idx].is_cited = True
#                     final_sources.append(processed_sources[idx])
#                     seen_indices.add(idx)

#         logger.info(f"LLM이 인용한 문서: {len(final_sources)}개")

#     # 점수 내림차순 정렬 (객체 자체 정렬)
#     sorted_candidates = sorted(
#         processed_sources, key=lambda x: x.relevance_score, reverse=True
#     )

#     for doc in sorted_candidates:
#         if len(final_sources) >= target_k:
#             break

#         idx = doc.index - 1
#         if idx in seen_indices:
#             continue

#         if (doc.relevance_score or 0.0) < sanity_threshold:
#             continue

#         final_sources.append(doc)
#         seen_indices.add(idx)

#     logger.info(f"최종 선별된 문서 수: {len(final_sources)}개 (Target K: {target_k})")

#     # 1순위: 인용 여부
#     # 2순위: Relevance Score 기준 내림차순
#     final_sources.sort(key=lambda x: (not x.is_cited, x.index))

#     return final_sources
