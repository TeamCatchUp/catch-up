from __future__ import annotations

import re
from re import DOTALL
from typing import Annotated
from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage
from langgraph.graph.message import add_messages

from catchup.langgraph.utils import ainvoke_llm_with_token_usage
from catchup.langgraph.utils import log_node
from catchup.prompts.loader import prompt_loader
from catchup.rag.constants import FALLBACK_ANSWER
from catchup.schemas.sources import BaseSource
from catchup.schemas.structures import SearchTurnMeta
from catchup.utils.documents import DocGroup
from catchup.utils.documents import build_doc_groups
from catchup.utils.documents import build_docs_summary
from catchup.utils.documents import deduplicate_documents
from catchup.utils.documents import extract_anchor_ids
from catchup.utils.documents import get_document_id
from catchup.utils.documents import render_grouped_context_text
from catchup.utils.documents import resolve_temporal_context

# node 로깅 데코레이터
logger = structlog.get_logger("catchup.graph")

__all__ = [
    "ainvoke_llm_with_token_usage",
    "build_doc_groups",
    "build_docs_summary",
    "deduplicate_documents",
    "extract_anchor_ids",
    "get_document_id",
    "log_node",
    "render_grouped_context_text",
    "resolve_temporal_context",
    "DocGroup",
]


def drop_orphaned_tool_calls(messages: list[BaseMessage]) -> list[BaseMessage]:
    """tool_calls가 있는 AIMessage 다음에 ToolMessage가 없는 orphan을 제거한다.

    히스토리 어디서든 AIMessage(tool_calls) 바로 다음 메시지가 ToolMessage가 아니면
    해당 AIMessage를 제거한다.
    """
    if not messages:
        return messages

    cleaned = []
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            next_msg = messages[i + 1] if i + 1 < len(messages) else None
            if not isinstance(next_msg, ToolMessage):
                logger.warning(
                    "dropping_orphaned_tool_call_message",
                    message_id=getattr(msg, "id", None),
                    position=i,
                )
                continue
        cleaned.append(msg)

    return cleaned


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

    filtered = [
        m
        for m in past
        if isinstance(m, HumanMessage)
        or (isinstance(m, AIMessage) and not getattr(m, "tool_calls", None))
    ]

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


def build_system_message(
    static_prompt: str,
    dynamic_prompts: list[str] | None = None,
    cache_prompt: bool = False,
    instructions_last: bool = False,
) -> SystemMessage:
    """시스템 메시지를 구성한다.

    instructions_last=True이면 Anthropic Long Context 가이드에 따라
    동적 프롬프트(데이터)를 정적 프롬프트(지시문) 앞에 배치한다.
    """
    static_block: dict = {"type": "text", "text": static_prompt}

    if cache_prompt:
        static_block["cache_control"] = {"type": "ephemeral"}

    if instructions_last:
        content: list[dict] = []
        if dynamic_prompts:
            for prompt in dynamic_prompts:
                if prompt:
                    content.append({"type": "text", "text": prompt})
        content.append(static_block)
    else:
        content = [static_block]
        if dynamic_prompts:
            for prompt in dynamic_prompts:
                if prompt:
                    content.append({"type": "text", "text": prompt})

    return SystemMessage(content=content)


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


def extract_search_reason(reasoning: str | None) -> str | None:
    """tool call 전 reasoning에서 <search_reason> 태그 내용을 추출한다.
    태그가 없으면 원문을 그대로 반환한다."""
    if not reasoning:
        return reasoning
    match = re.search(r"<search_reason>(.*?)</search_reason>", reasoning, re.DOTALL)
    if match:
        return match.group(1).strip() or reasoning
    return reasoning


async def dispatch_search_reason(tool_calls: list, node_name: str) -> None:
    """검색 툴 호출의 reason 파라미터를 프론트엔드 process 이벤트로 dispatch한다.

    tool_choice=any 환경에서 텍스트 출력 없이 tool args에서 reasoning을 추출한다.
    single_query_search 또는 multi_query_search 중 첫 번째 호출의 reason을 사용한다.
    """
    from langchain_core.callbacks import adispatch_custom_event

    search_call = next(
        (tc for tc in tool_calls if tc["name"] in ("single_query_search", "multi_query_search")),
        None,
    )
    if not search_call:
        return
    reason = search_call["args"].get("reason", "")
    if reason:
        await adispatch_custom_event(
            "process",
            {"status": "completed", "node": node_name, "reasoning": reason},
        )


def map_indices_to_doc_ids(
    indices: list[int],
    accumulated_docs: list[Document],
    agent_seen_ids: list[str],
) -> set[str]:
    """submit_result의 key_document_indices (1-based)를 실제 doc ID set으로 변환한다.

    agent_seen_ids 순서 기준으로 매핑해 ToolMessage global index와 일치시킨다.
    agent_seen_ids가 비어있으면 accumulated_docs 순서로 fallback한다.
    """
    id_to_doc = {get_document_id(d): d for d in accumulated_docs}
    ordered = [id_to_doc[sid] for sid in agent_seen_ids if sid in id_to_doc]
    docs = ordered or accumulated_docs

    result: set[str] = set()
    for idx in indices:
        if 1 <= idx <= len(docs):
            doc_id = get_document_id(docs[idx - 1])
            if doc_id:
                result.add(doc_id)
    return result


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
    out = _INLINE_BRACKET_INDEX_PATTERN.sub("", reasoning)
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


def parse_citations(full_answer: str) -> tuple[str, set[str]]:
    body_part = full_answer
    cited_indices: set[str] = set()

    match = re.search(r"<citations>(.*?)</citations>", full_answer, DOTALL)
    if match:
        body_part = full_answer[: match.start()].strip()
        raw = match.group(1).strip()
        if raw:
            cited_indices = {s.strip() for s in raw.split(",") if s.strip().isdigit()}

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
