import asyncio
import functools
import json
import re
import time
from collections import Counter
from re import DOTALL
from typing import Annotated
from typing import Any
from typing import Awaitable
from typing import Callable

import structlog
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langgraph.graph.message import add_messages

from catchup.costs.utils import extract_token_usages
from catchup.prompts.loader import prompt_loader
from catchup.rag.policies import FALLBACK_ANSWER
from catchup.rag.schemas.sources import BaseSource

# node 로깅 데코레이터
logger = structlog.get_logger("catchup.graph")


def drop_orphaned_tool_calls(messages: list[BaseMessage]) -> list[BaseMessage]:
    """마지막 AIMessage에 tool_calls가 있지만 ToolMessage가 없는 경우 제거한다."""
    if not messages:
        return messages
    last = messages[-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        logger.warning(
            "dropping_orphaned_tool_call_message", message_id=getattr(last, "id", None)
        )
        return list(messages[:-1])
    return messages


def build_docs_summary(docs: list[Document], max_docs: int = 10) -> str:
    """Agent가 현재까지 수집된 지식의 '내용'을 파악할 수 있도록 요약 제공."""
    if not docs:
        return "No documents collected yet."

    source_counts = Counter(d.metadata.get("source", "unknown") for d in docs)
    source_str = ", ".join(f"{src}:{cnt}" for src, cnt in source_counts.items())
    lines = [
        f"Total {len(docs)}docs accumulated ({source_str})",
        "Recently collected documents:",
    ]

    for i, doc in enumerate(docs[:max_docs], 1):
        source = doc.metadata.get("source", "unknown")
        temporal = resolve_temporal_context(doc.metadata)

        # Confluence는 원문 청크이므로 길이를 제한, 나머지는 요약본이므로 전문 활용
        if source == "confluence":
            content = doc.page_content[:800].replace("\n", " ")
            if len(doc.page_content) > 800:
                content += "..."
        else:
            # Slack, Jira, GitHub 등은 page_content가 이미 영문 요약본
            content = doc.page_content.replace("\n", " ")

        lines.append(f"[{i}] ({source}) {temporal}\n    {content}")

    if len(docs) > max_docs:
        lines.append(
            f"... and {len(docs) - max_docs} more document(s) stored in memory."
        )

    return "\n".join(lines)


async def ainvoke_llm_with_token_usage(
    llm: Any,
    messages: list[BaseMessage],
    semaphore: Any = None,
    timeout: float | None = None,
    **kwargs: Any,
) -> tuple[Any, dict]:
    """LLM을 호출하고 토큰 사용량을 추출한다. 에러 발생 시 예외를 전파한다."""
    token_usages = {"token_breakdown": {}}
    try:
        async with asyncio.timeout(timeout):
            if semaphore:
                t_sem = time.perf_counter()
                logger.debug(
                    "semaphore_acquiring",
                    semaphore=semaphore.name,
                )
                async with semaphore:
                    t_llm = time.perf_counter()
                    logger.debug(
                        "llm_invoke_start",
                        semaphore_wait_elapsed=round(t_llm - t_sem, 3),
                    )
                    response = await llm.ainvoke(input=messages, **kwargs)
            else:
                t_llm = time.perf_counter()
                logger.debug("llm_invoke_without_semaphore_start")
                response = await llm.ainvoke(input=messages, **kwargs)

        logger.debug(
            "llm_invoke_completed", elapsed=round(time.perf_counter() - t_llm, 3)
        )

        # response가 dict인 경우 (with_structured_output include_raw=True) 처리
        raw_response = response.get("raw") if isinstance(response, dict) else response
        token_usages = extract_token_usages(raw_response)
        return response, token_usages

    except asyncio.TimeoutError as e:
        logger.warning(
            "llm_call_timeout",
            timeout=timeout,
            error=str(e),
            exc_info=True,
        )
        raise e
    except Exception as e:
        logger.warning("llm_call_failed", error=str(e), exc_info=True)
        raise e


# 사용자-어시스턴트 대화 전처리 함수들
def filter_conversation(messages: Annotated[list, add_messages]):
    return [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]


def get_formatted_history_text(
    conversation_history: list[HumanMessage | AIMessage],
) -> str:
    return "\n".join([f"{msg.type}: {msg.content}" for msg in conversation_history])


def get_conversation_history(messages: Annotated[list, add_messages]):
    """현재 턴 이전의 대화 이력만 반환한다.

    에이전트 루프 후에는 state["messages"]에 AIMessage(tool_calls)와 ToolMessage가
    섞이므로, 단순 [:-1] 트릭 대신 마지막 HumanMessage 기준으로 현재 턴을 분리한다.
    이전 턴에서도 tool_calls AIMessage와 ToolMessage를 제외하고, 연속된 AIMessage는
    마지막 것만 유지해 최종 답변만 히스토리에 포함시킨다.
    """
    # 마지막 HumanMessage = 현재 턴 시작점
    last_human_idx = next(
        (
            i
            for i in range(len(messages) - 1, -1, -1)
            if isinstance(messages[i], HumanMessage)
        ),
        -1,
    )
    if last_human_idx <= 0:
        return []

    past = messages[:last_human_idx]

    # tool_calls 있는 AIMessage(에이전트 검색 결정)와 ToolMessage는 파이프라인 내부 메시지 → 제외
    filtered = [
        m
        for m in past
        if isinstance(m, HumanMessage)
        or (isinstance(m, AIMessage) and not getattr(m, "tool_calls", None))
    ]

    # 연속된 AIMessage → 마지막 것만 유지 (에이전트 stop 메시지 대신 최종 답변만 남김)
    condensed: list = []
    for m in filtered:
        if (
            isinstance(m, AIMessage)
            and condensed
            and isinstance(condensed[-1], AIMessage)
        ):
            condensed[-1] = m
        else:
            condensed.append(m)

    return condensed[-6:]


def get_latest_query(messages: Annotated[list, add_messages]):
    return next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )


def build_confirmed_priority_prompt(
    retrieved_docs: list[Document],
    confirmed_essential_doc_ids: list[str] | None,
) -> str | None:
    """confirmed_essential_doc_ids를 retrieved_docs 내 1-base 인덱스로 매핑해
    confirmed_priority_documents 프롬프트 블록을 렌더링한다.

    매핑 가능한 인덱스가 없으면 None을 반환 (호출자가 dynamic_prompts에서 제외)."""
    if not confirmed_essential_doc_ids:
        return None
    confirmed_id_set = set(confirmed_essential_doc_ids)
    confirmed_indices = [
        i for i, doc in enumerate(retrieved_docs, start=1)
        if get_document_id(doc) in confirmed_id_set
    ]
    if not confirmed_indices:
        return None
    return prompt_loader.get_prompt(
        "common/confirmed_priority_documents",
        confirmed_priority_indices=confirmed_indices,
    )


def prepare_retrieved_context_text(documents: list[Document]) -> str:
    parts = []
    for i, doc in enumerate(documents, start=1):
        source = doc.metadata.get("source", "unknown")
        content = doc.metadata.get("contextual_content", "")
        temporal = resolve_temporal_context(doc.metadata)
        part = f"[{i}] (Source: {source})\n{content} {temporal}"
        if source == "confluence":
            part = part + f"\nstatus: {doc.metadata.get('status', '')}"
        parts.append(part)
    return "\n\n".join(parts)


def build_system_message(
    static_prompt: str,
    dynamic_prompts: list[str] | None = None,
    cache_prompt: bool = False,
) -> SystemMessage:

    # 정적 프롬프트 (캐싱 대상)
    static_block: dict = {"type": "text", "text": static_prompt}

    if cache_prompt:
        static_block["cache_control"] = {"type": "ephemeral"}
        # TODO: langchain-aws 지원 시점에 "ttl": "1h" 추가

    content = [static_block]

    # 동적 프롬프트
    if dynamic_prompts:
        for prompt in dynamic_prompts:
            content.append({"type": "text", "text": prompt})

    return SystemMessage(content=content)


def resolve_temporal_context(metadata: dict) -> str:
    temporal_fields = [
        "created_at",
        "updated_at",
        "resolved_at",
        "due_date",
        "edited_at",
        "closed_at",
        "merged_at",
        "committed_at",
    ]

    parts = [
        f"{field}: {str(metadata[field])}"
        for field in temporal_fields
        if metadata.get(field)
    ]

    return " | ".join(parts) if parts else ""


def extract_anchor_ids(documents: list[Document]) -> list[str]:
    anchors = [doc.id for doc in documents if doc.id]
    return list(dict.fromkeys(anchors))  # 중복 제거 & 순서 유지


def get_document_id(doc: Document) -> str:
    """문서의 고유 ID를 반환합니다. ID가 없으면 내용의 해시값을 사용한다."""
    doc_id = doc.id if doc.id else hash(doc.page_content)
    return str(doc_id)


def deduplicate_documents(documents: list[Document]) -> list[Document]:
    """문서 리스트에서 ID 또는 내용 해시를 기준으로 중복을 제거하고 순서를 유지한다."""
    unique_docs = []
    seen_ids = set()
    for doc in documents:
        doc_id = get_document_id(doc)
        if doc_id not in seen_ids:
            unique_docs.append(doc)
            seen_ids.add(doc_id)
    return unique_docs


def coerce_message_text(content: Any) -> str:
    """BaseMessage.content를 일반 텍스트로 정규화한다.

    extended_thinking이 켜진 모델은 content가 블록 리스트로 옴
    ([{"type": "thinking", ...}, {"type": "text", "text": "..."}]).
    이 경우 text 블록의 텍스트만 이어 붙이고, 그 외에는 str(content)을 반환한다.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content) if content is not None else ""


def extract_essential_ids(reasoning: str | None, docs: list[Document]) -> set[str]:
    """
    Agent의 reasoning에서 [Key Document Indices]를 추출하여 실제 문서 ID(또는 해시) 세트로 변환한다.
    마크다운 강조(**n**), 대괄호([n]), 콤마/공백 구분 등 다양한 형식을 지원.
    """
    if not reasoning or not docs:
        return set()

    # 1. [Key Document Indices]: 이후의 텍스트를 추출한다.
    # 대소문자 무시 및 유연한 매칭을 수행한다.
    pattern = r"\[Key Document Indices\]:\s*(.*)"
    match = re.search(pattern, reasoning, re.IGNORECASE)
    if not match:
        # 패턴 자체가 없으면 조용히 반환한다 (에이전트가 지목을 안 한 경우일 수 있음).
        return set()

    content = match.group(1).split("\n")[0] # 첫 줄만 취한다.

    # 2. 숫자만 모두 추출한다 (마크다운 등 특수문자 제거 효과).
    indices = [int(s) for s in re.findall(r"\d+", content)]

    
    if not indices:
        logger.warning("essential_indices_not_found_in_pattern", text=content)
        return set()

    essential_ids = set()
    invalid_indices = []
    for idx in indices:
        # 에이전트가 사용하는 인덱스는 1-based
        if 1 <= idx <= len(docs):
            doc = docs[idx - 1]
            essential_ids.add(get_document_id(doc))
        else:
            invalid_indices.append(idx)

    if invalid_indices:
        logger.warning("agent_cited_out_of_range_indices", invalid=invalid_indices, max_range=len(docs))

    if essential_ids:
        logger.debug("essential_ids_extracted", count=len(essential_ids), ids=list(essential_ids))

    return essential_ids


def parse_citations(full_answer: str) -> tuple[str, dict[str, str]]:
    body_part = full_answer
    citation_dict = {}

    # 정상 동작: 태그가 완전히 닫힘. (<citations>...</citations>)
    match = re.search(r"<citations>(.*?)</citations>", full_answer, DOTALL)
    if match:
        body_part = full_answer[: match.start()].strip()
        try:
            citation_dict = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            logger.warning("citations_parsing_failed")

    # 비정상 동작: 태그가 열리거나 불완전함. (<citations>...)
    elif open_tag_match := re.search(r"<citations>", full_answer):
        logger.warning(
            "citations_block_truncated",
            context="token_overflow",
        )
        body_part = full_answer[: open_tag_match.start()].strip()
        if not body_part:
            body_part = FALLBACK_ANSWER

    return body_part, citation_dict


def mark_citations(
    candidate_sources: list[BaseSource],
    citations: dict[str, str],
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


def log_node(func: Callable[..., Awaitable[dict]]):
    """
    LangGraph 노드 실행 전후로 로깅을 수행하는 데코레이터
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):

        node_name = func.__name__
        start_time = time.perf_counter()

        logger.info("node_started", node_name=node_name)

        try:
            result = await func(*args, **kwargs)

            elapsed = time.perf_counter() - start_time
            logger.info(
                "node_completed", node_name=node_name, duration=round(elapsed, 4)
            )

            return result

        except Exception as e:
            logger.error(
                "node_failed", node_name=node_name, error=str(e), exc_info=True
            )
            raise e

    return wrapper
