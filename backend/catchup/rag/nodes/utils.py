from __future__ import annotations

import asyncio
import functools
import re
import time
from collections import Counter
from dataclasses import dataclass
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
from catchup.rag.schemas.structures import SearchTurnMeta

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


def build_search_history_summary(snapshots: list) -> str:
    """search_turn_history를 supervisor용 경량 요약으로 변환한다.

    리스트 내 순서(1-based)가 supervisor에게 노출되는 검색 턴 ID 역할을 한다.
    마지막 항목은 hot cache(previously_retrieved_documents에 전문 표시)임을 명시한다.

    체크포인터 복원 시 dict로 역직렬화될 수 있으므로 dict/Pydantic 모두 처리한다.
    """
    if not snapshots:
        return ""

    lines = []
    last_idx = len(snapshots)

    for i, raw in enumerate(snapshots, 1):
        snap = SearchTurnMeta.model_validate(raw) if isinstance(raw, dict) else raw
        src_str = ", ".join(
            f"{src}:{cnt}" for src, cnt in snap.source_distribution.items()
        )
        total = sum(snap.source_distribution.values())
        label = f"[Search {i}] (hot cache)" if i == last_idx else f"[Search {i}]"
        lines.append(
            f'{label}\n'
            f'Query: "{snap.rewritten_query}"\n'
            f'Sources: {src_str} ({total} docs)'
        )

    return "\n\n".join(lines)


def build_docs_summary(docs: list[Document], max_docs: int = 20) -> str:
    """Agent가 현재까지 수집된 지식의 '내용'을 파악할 수 있도록 요약 제공."""
    if not docs:
        return ""

    source_counts = Counter(d.metadata.get("source", "unknown") for d in docs)
    source_str = ", ".join(f"{src}:{cnt}" for src, cnt in source_counts.items())
    lines = [
        f"Total {len(docs)}docs accumulated ({source_str})",
        "Recently collected documents:",
    ]

    for i, doc in enumerate(docs[:max_docs], 1):
        source = doc.metadata.get("source", "unknown")
        temporal = resolve_temporal_context(doc.metadata)

        raw = doc.page_content[:300].strip()
        if len(doc.page_content) > 300:
            raw += "..."
        content = re.sub(r"[ \t]+", " ", raw)
        content = re.sub(r"\n{3,}", "\n\n", content)

        lines.append(f"[{i}] ({source}) {temporal}\n{content}")

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
    groups: list[DocGroup],
    confirmed_essential_doc_ids: list[str] | None,
) -> str | None:
    """confirmed_essential_doc_ids를 groups 내 1-base 인덱스로 매핑해
    confirmed_priority_documents 프롬프트 블록을 렌더링한다.

    그룹 내 어느 청크 하나라도 confirmed 셋에 포함되면 해당 그룹 인덱스를 추가한다.
    매핑 가능한 인덱스가 없으면 None을 반환 (호출자가 dynamic_prompts에서 제외)."""
    if not confirmed_essential_doc_ids:
        return None
    confirmed_id_set = set(confirmed_essential_doc_ids)
    confirmed_indices = [
        group.display_index
        for group in groups
        if any(get_document_id(d) in confirmed_id_set for d in group.docs)
    ]
    if not confirmed_indices:
        return None
    return prompt_loader.get_prompt(
        "common/confirmed_priority_documents",
        confirmed_priority_indices=confirmed_indices,
    )


# --- Document grouping for chunked sources (Confluence pages, ChannelTalk articles) ---
# 같은 문서에서 나온 여러 청크가 LLM에게는 별개의 인용 인덱스로 보여 사용자에게
# 같은 출처가 중복 노출되는 문제를 막기 위해, context 빌드 시 한 인덱스 아래로 묶는다.
# 그룹 내부에는 chunk_index 오름차순으로 배치하고, 누락된 청크 사이에는
# ...(Omitted)... 마커를 넣어 LLM이 문맥 단절을 인지하게 한다.

@dataclass
class DocGroup:
    display_index: int  # LLM에 노출되는 1-base 인덱스
    docs: list[Document]  # 그룹 멤버. 청크 그룹은 chunk_index ASC, 단일은 길이 1
    representative: Document  # BaseSource 빌드용 대표 청크 (그룹 내 최상위 스코어 문서)
    is_chunked: bool  # 청크 그룹핑이 적용되었는지


def _chunk_meta(doc: Document) -> tuple[int | None, int | None]:
    """청킹된 source(Confluence, ChannelTalk article)에서 (chunk_index, total)을 반환.
    그렇지 않으면 (None, None)."""
    md = doc.metadata
    source = md.get("source")
    if source == "confluence":
        return md.get("chunk_index"), md.get("total_chunks")
    if source == "channel_talk" and md.get("entity_type") == "document_article":
        chunk = md.get("document_article_core", {}).get("chunk", {}) or {}
        return chunk.get("chunk_index"), chunk.get("chunk_count")
    return None, None


def _group_key(doc: Document) -> str | None:
    """청크 그룹 키. doc.id에서 ':chunk:N' 접미사를 떼어 그룹을 식별한다.
    그룹 대상이 아니면 None."""
    md = doc.metadata
    source = md.get("source")
    is_groupable = source == "confluence" or (
        source == "channel_talk" and md.get("entity_type") == "document_article"
    )
    if not is_groupable:
        return None
    doc_id = getattr(doc, "id", None)
    if not doc_id or ":chunk:" not in doc_id:
        return None
    return doc_id.rsplit(":chunk:", 1)[0]


def build_doc_groups(retrieved_docs: list[Document]) -> list[DocGroup]:
    """
    retrieved_docs 내 문서를 그룹 단위로 묶는다.

    그룹 위치는 첫 등장(=최상위 랭크) 청크 기준이며, 그룹 내부는 chunk_index ASC.
    그룹 대상이 아닌 doc은 단일 멤버 그룹으로 보존한다.
    """
    groups: list[DocGroup] = []
    key_to_group: dict[str, DocGroup] = {}

    for doc in retrieved_docs:
        gkey = _group_key(doc)
        if gkey is None:
            groups.append(
                DocGroup(
                    display_index=len(groups) + 1,
                    docs=[doc],
                    representative=doc,
                    is_chunked=False,
                )
            )
            continue
        existing = key_to_group.get(gkey)
        if existing is None:
            new_group = DocGroup(
                display_index=len(groups) + 1,
                docs=[doc],
                representative=doc,
                is_chunked=False,
            )
            groups.append(new_group)
            key_to_group[gkey] = new_group
        else:
            existing.docs.append(doc)
            existing.is_chunked = True

    # 청크 그룹은 chunk_index ASC로 내부 정렬 (그룹 외부 순서는 유지).
    for group in groups:
        if group.is_chunked:
            group.docs.sort(key=lambda d: _chunk_meta(d)[0] or 0)

    return groups


def _render_chunk_group(group: DocGroup) -> str:
    """청크 그룹을 단일 인덱스 블록으로 렌더링."""
    rep = group.representative
    md = rep.metadata
    source = md.get("source", "unknown")
    title = md.get("title") or ""
    temporal = resolve_temporal_context(md)

    header_bits = [f"[{group.display_index}] (Source: {source})"]
    if title:
        header_bits.append(f'Title: "{title}"')
    if temporal:
        header_bits.append(temporal)
    header = " ".join(header_bits)

    lines: list[str] = [header]

    # 누락된 청크 사이에는 ...(Omitted)... 마커를 넣어 LLM이 문맥 단절을 인지하게 한다.
    prev_idx: int | None = None
    for doc in group.docs:
        chunk_idx, total = _chunk_meta(doc)
        if chunk_idx is None:
            chunk_label = "chunk ?"
        elif total is not None:
            chunk_label = f"chunk {chunk_idx + 1}/{total}"
        else:
            chunk_label = f"chunk {chunk_idx + 1}"
        if (
            prev_idx is not None
            and chunk_idx is not None
            and chunk_idx > prev_idx + 1
        ):
            lines.append("...(Omitted)...")
        lines.append(f"--- {chunk_label} ---")
        lines.append(doc.metadata.get("contextual_content", ""))
        prev_idx = chunk_idx

    # 누락된 마지막 청크 표기 (예: total 5인데 마지막이 4번까지만 등장).
    if group.docs:
        last_idx, total = _chunk_meta(group.docs[-1])
        if (
            last_idx is not None
            and total is not None
            and last_idx < total - 1
        ):
            lines.append("...(Omitted)...")

    if source == "confluence":
        lines.append(f"status: {md.get('status', '')}")

    return "\n".join(lines)


def render_grouped_context_text(groups: list[DocGroup]) -> str:
    """
    그룹 리스트로부터 LLM에게 제공할 retrieved_context 텍스트를 생성한다.
    """
    parts: list[str] = []
    for group in groups:
        if group.is_chunked:
            parts.append(_render_chunk_group(group))
            continue
        # 단일 doc — 기존 포맷 유지.
        doc = group.representative
        md = doc.metadata
        source = md.get("source", "unknown")
        content = md.get("contextual_content", "")
        temporal = resolve_temporal_context(md)
        part = f"[{group.display_index}] (Source: {source})\n{content} {temporal}"
        if source == "confluence":
            part = part + f"\nstatus: {md.get('status', '')}"
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


_KEY_DOC_INDICES_TAG_PATTERN = re.compile(
    r"<\s*key_document_indices\s*>(.*?)<\s*/\s*key_document_indices\s*>",
    re.IGNORECASE | re.DOTALL,
)

_REASON_FOR_STOPPING_PATTERN = re.compile(
    r"<\s*reason_for_stopping\s*>(.*?)<\s*/\s*reason_for_stopping\s*>",
    re.IGNORECASE | re.DOTALL,
)


def extract_reason_for_stopping(reasoning: str | None) -> str | None:
    """agent_reasoning에서 <reason_for_stopping> 태그 내용을 추출한다.
    태그가 없으면 None을 반환한다."""
    if not reasoning:
        return None
    match = _REASON_FOR_STOPPING_PATTERN.search(reasoning)
    if not match:
        return None
    return match.group(1).strip() or None


# 본문 안의 인덱스 좌표 패턴들. agent_reasoning은 reuse 턴에 재공급되거나 grouping
# 도입 후 인덱스 체계가 바뀌므로, 산문 안에 박힌 [N]/**N**/N번 문서 좌표는 모두
# stale로 간주하고 제거한다. 정확한 인덱스 신호는 confirmed_priority_documents
# 블록으로 별도 전달된다.
_INLINE_BRACKET_INDEX_PATTERN = re.compile(r"\[\d+\]")
_BOLD_BARE_NUMBER_PATTERN = re.compile(r"\*\*\d+\*\*")
_KOREAN_NUMBER_DOC_PATTERN = re.compile(r"\d+\s*번\s*문서")


def sanitize_agent_reasoning(reasoning: str | None) -> str | None:
    """답변 LLM에 넘기기 전, agent_reasoning에서 stale한 인덱스 좌표를 모두 제거한다.

    제거 대상:
    - <key_document_indices>...</key_document_indices> 블록
    - 본문 안의 inline `[N]` (숫자만, `[note]` 같은 식별자는 보존)
    - `**N**` 마크다운 강조 (숫자만)
    - "N번 문서" 한국어 표현

    rerank/grouping 이후 또는 reuse 턴에서는 좌표가 의미를 잃으므로, 좌표 자체를
    탈색해 환각 인용을 차단한다. 정확한 인덱스 신호는 confirmed_priority_documents
    블록으로 별도 전달된다.
    """
    if not reasoning:
        return reasoning
    out = _KEY_DOC_INDICES_TAG_PATTERN.sub("", reasoning)
    out = _INLINE_BRACKET_INDEX_PATTERN.sub("", out)
    out = _BOLD_BARE_NUMBER_PATTERN.sub("", out)
    out = _KOREAN_NUMBER_DOC_PATTERN.sub("", out)
    return out.strip()


def scrub_orphan_indices(body: str, valid_indices: set[int]) -> str:
    """
    답변 본문에서 현재 표시 인덱스 범위 밖의 `[N]` 참조를 제거한다.

    LLM이 stale agent_reasoning이나 환각으로 out-of-range `[N]`을 본문에 박는
    경우를 막아, 프론트가 깨진 인용 아이콘을 그리지 않게 한다. 유효한 인덱스의
    `[N]`은 그대로 유지된다.
    """
    if not body:
        return body

    def _replace(match: re.Match) -> str:
        idx = int(match.group(1))
        return match.group(0) if idx in valid_indices else ""

    return re.sub(r"\[(\d+)\]", _replace, body)


def extract_essential_ids(reasoning: str | None, docs: list[Document]) -> set[str]:
    """
    Agent의 reasoning에서 <key_document_indices> 태그를 추출하여 실제 문서 ID 세트로 변환한다.
    마크다운 강조(**n**), 대괄호([n]), 콤마/공백 구분 등 다양한 내부 형식을 지원.
    """
    if not reasoning or not docs:
        return set()

    match = _KEY_DOC_INDICES_TAG_PATTERN.search(reasoning)
    if not match:
        # 태그가 없으면 조용히 반환한다 (에이전트가 지목을 안 한 경우일 수 있음).
        return set()

    content = match.group(1)

    # 숫자만 모두 추출한다 (마크다운 등 특수문자 제거 효과).
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


def parse_citations(full_answer: str) -> tuple[str, set[str]]:
    body_part = full_answer
    cited_indices: set[str] = set()

    # 정상 동작: 태그가 완전히 닫힘. (<citations>1, 3, 4</citations>)
    match = re.search(r"<citations>(.*?)</citations>", full_answer, DOTALL)
    if match:
        body_part = full_answer[: match.start()].strip()
        raw = match.group(1).strip()
        if raw:
            cited_indices = {s.strip() for s in raw.split(",") if s.strip().isdigit()}

    # 비정상 동작: 태그가 열리거나 불완전함. (<citations>...)
    elif open_tag_match := re.search(r"<citations>", full_answer):
        logger.warning(
            "citations_block_truncated",
            context="token_overflow",
        )
        body_part = full_answer[: open_tag_match.start()].strip()
        if not body_part:
            body_part = FALLBACK_ANSWER

    return body_part, cited_indices


def mark_citations(
    candidate_sources: list[BaseSource],
    citations: set[str],
) -> list[BaseSource]:

    final_sources = []

    for source in candidate_sources:
        source.is_cited = str(source.index) in citations
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
