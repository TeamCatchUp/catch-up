from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from langchain_core.documents import Document


@dataclass
class DocGroup:
    display_index: int  # LLM에 노출되는 1-base 인덱스
    docs: list[Document]  # 그룹 멤버. 청크 그룹은 chunk_index ASC, 단일은 길이 1
    representative: Document  # BaseSource 빌드용 대표 청크 (그룹 내 최상위 스코어 문서)
    is_chunked: bool  # 청크 그룹핑이 적용되었는지


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


def get_document_id(doc: Document) -> str:
    """문서의 고유 ID를 반환한다. ID가 없으면 내용의 해시값을 사용한다."""
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


def extract_anchor_ids(documents: list[Document]) -> list[str]:
    anchors = [doc.id for doc in documents if doc.id]
    return list(dict.fromkeys(anchors))  # 중복 제거 & 순서 유지


def build_docs_summary(
    docs: list[Document], max_docs: int = 20, start_index: int = 1
) -> str:
    """Agent가 현재까지 수집된 지식의 '내용'을 파악할 수 있도록 XML 형식 요약을 제공한다.

    start_index: ToolMessage의 전역 인덱스 오프셋. 기본값 1(1-based).
    search_tool_executor에서 호출 시 global index를 유지하기 위해 사용한다.
    """
    if not docs:
        return ""

    source_counts = Counter(d.metadata.get("source", "unknown") for d in docs)
    source_str = ", ".join(f"{src}:{cnt}" for src, cnt in source_counts.items())

    _TRUNCATE_SOURCES = {"confluence", "channel_talk"}
    _TRUNCATE_LIMIT = 500

    doc_elements: list[str] = []
    for i, doc in enumerate(docs[:max_docs], start_index):
        source = doc.metadata.get("source", "unknown")
        temporal = resolve_temporal_context(doc.metadata)

        if source in _TRUNCATE_SOURCES:
            raw = doc.page_content[:_TRUNCATE_LIMIT].strip()
            if len(doc.page_content) > _TRUNCATE_LIMIT:
                raw += "..."
        else:
            raw = doc.page_content.strip()
        content = re.sub(r"[ \t]+", " ", raw)
        content = re.sub(r"\n{3,}", "\n\n", content)
        if temporal:
            content = f"{content}\n{temporal}"

        parts = [
            f'<document index="{i}">',
            f"  <source>{source}</source>",
            f"  <document_content>\n{content}\n  </document_content>",
            "</document>",
        ]
        doc_elements.append("\n".join(parts))

    trailing = ""
    if len(docs) > max_docs:
        trailing = f"\n<!-- {len(docs) - max_docs} more document(s) stored in memory -->"

    inner = "\n".join(doc_elements)
    return f'<documents total="{len(docs)}" sources="{source_str}">\n{inner}\n</documents>{trailing}'


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


# --- Document grouping for chunked sources (Confluence pages, ChannelTalk articles) ---
# 같은 문서에서 나온 여러 청크가 LLM에게는 별개의 인용 인덱스로 보여 사용자에게
# 같은 출처가 중복 노출되는 문제를 막기 위해, context 빌드 시 한 인덱스 아래로 묶는다.
# 그룹 내부에는 chunk_index 오름차순으로 배치하고, 누락된 청크 사이에는
# ...(Omitted)... 마커를 넣어 LLM이 문맥 단절을 인지하게 한다.


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

    for group in groups:
        if group.is_chunked:
            group.docs.sort(key=lambda d: _chunk_meta(d)[0] or 0)

    return groups


def _render_chunk_group(group: DocGroup) -> str:
    """청크 그룹을 XML document 엘리먼트로 렌더링한다."""
    rep = group.representative
    md = rep.metadata
    source = md.get("source", "unknown")
    title = md.get("title") or ""
    temporal = resolve_temporal_context(md)

    inner_lines: list[str] = []

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
            inner_lines.append("...(Omitted)...")
        inner_lines.append(f"--- {chunk_label} ---")
        inner_lines.append(doc.metadata.get("contextual_content", ""))
        prev_idx = chunk_idx

    if group.docs:
        last_idx, total = _chunk_meta(group.docs[-1])
        if (
            last_idx is not None
            and total is not None
            and last_idx < total - 1
        ):
            inner_lines.append("...(Omitted)...")

    if temporal:
        inner_lines.append(temporal)

    content_text = "\n".join(inner_lines)

    parts: list[str] = [f'<document index="{group.display_index}">']
    parts.append(f"  <source>{source}</source>")
    if title:
        parts.append(f"  <title>{title}</title>")
    parts.append(f"  <document_content>\n{content_text}\n  </document_content>")
    if source == "confluence":
        parts.append(f"  <status>{md.get('status', '')}</status>")
    parts.append("</document>")

    return "\n".join(parts)


def render_grouped_context_text(groups: list[DocGroup]) -> str:
    """그룹 리스트로부터 LLM에게 제공할 retrieved_context XML을 생성한다."""
    doc_elements: list[str] = []
    for group in groups:
        if group.is_chunked:
            doc_elements.append(_render_chunk_group(group))
            continue
        doc = group.representative
        md = doc.metadata
        source = md.get("source", "unknown")
        content = md.get("contextual_content", "")
        temporal = resolve_temporal_context(md)

        content_text = content
        if temporal:
            content_text = f"{content}\n{temporal}"

        parts: list[str] = [f'<document index="{group.display_index}">']
        parts.append(f"  <source>{source}</source>")
        parts.append(
            f"  <document_content>\n{content_text}\n  </document_content>"
        )
        if source == "confluence":
            parts.append(f"  <status>{md.get('status', '')}</status>")
        parts.append("</document>")

        doc_elements.append("\n".join(parts))

    inner = "\n".join(doc_elements)
    return f"<documents>\n{inner}\n</documents>"
