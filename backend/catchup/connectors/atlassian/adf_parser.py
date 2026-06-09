"""
Atlassian Document Format Parser
"""
from dataclasses import dataclass
from typing import Any


# ──────────────────────────────────────────
# DTO
# ──────────────────────────────────────────
@dataclass
class AdfMention:
    account_id: str
    display_name: str | None = None
    text: str | None = None

@dataclass
class AdfMedia:
    """
    ADF 문서 내 미디어/첨부파일
    """
    id: str
    collection: str | None = None
    type: str | None = None
    alt: str | None = None
    filename: str | None = None
    url : str | None = None

# ──────────────────────────────────────────
# 텍스트 변환
# ──────────────────────────────────────────
def adf_to_text(adf: dict) -> str:
    """
    ADF JSON → 평문 텍스트 변환

    지원 노드 타입:
    - text: 텍스트 (링크 mark 포함 시 URL 병기)
    - paragraph: 줄바꿈 구분
    - hardBreak: 줄바꿈
    - mention: @멘션 텍스트
    - inlineCard: URL 카드
    - emoji: shortName (:thumbsup: 등)
    - 기타: 재귀적으로 content 탐색

    Args:
        adf: ADF 형식 dict (최상위 type="doc")

    Returns:
        평문 텍스트 문자열
    """
    texts: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            node_type = node.get("type")

            if node_type == "text":
                text = node.get("text", "")
                marks = node.get("marks", [])
                for mark in marks:
                    if mark.get("type") == "link":
                        url = mark.get("attrs", {}).get("href", "")
                        if url and url != text:
                            text = f"{text} ({url})"
                            break
                texts.append(text)

            elif node_type == "hardBreak":
                texts.append("\n")

            elif node_type == "paragraph":
                for child in node.get("content", []):
                    _walk(child)
                texts.append("\n")

            elif node_type == "mention":
                attrs = node.get("attrs", {})
                mention_text = attrs.get("text", "")
                if mention_text:
                    if not mention_text.startswith("@"):
                        mention_text = f"@{mention_text}"
                    texts.append(mention_text)

            elif node_type == "inlineCard":
                url = node.get("attrs", {}).get("url", "")
                if url:
                    texts.append(f"[{url}]")

            elif node_type == "emoji":
                short_name = node.get("attrs", {}).get("shortName", "")
                if short_name:
                    texts.append(short_name)

            else:
                for child in node.get("content", []):
                    _walk(child)

        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(adf.get("content", []))
    return "".join(texts).strip()

def extract_text(content: Any) -> str:
    """
    Atlassian 컨텐츠 필드 → 평문 텍스트

    ADF dict이면 adf_to_text()로 변환하고,
    이미 문자열이면 그대로 반환한다.

    Args:
        content: ADF dict, 문자열, 또는 None

    Returns:
        평문 텍스트 문자열
    """
    if not content:
        return ""

    if isinstance(content, str):
        return content

    if not isinstance(content, dict):
        return str(content)

    if content.get("type") == "doc":
        return adf_to_text(content)

    return str(content)


# ──────────────────────────────────────────
# 멘션 추출
# ──────────────────────────────────────────

def extract_mentions(adf: dict) -> list[AdfMention]:
    """
    ADF에서 @멘션 노드를 재귀적으로 추출

    Args:
        adf: ADF 형식 dict

    Returns:
        AdfMention 리스트
    """
    mentions: list[AdfMention] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "mention":
                attrs = node.get("attrs", {})
                account_id = attrs.get("id", "")
                if account_id:
                    mentions.append(AdfMention(
                        account_id=account_id,
                        display_name=attrs.get("text"),
                        text=attrs.get("text"),
                    ))
            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(adf.get("content", []))
    return mentions


# ──────────────────────────────────────────
# 미디어 추출
# ──────────────────────────────────────────

def extract_media(adf: dict, site_url: str = "") -> list[AdfMedia]:
    """
    ADF에서 media/mediaGroup/mediaSingle 노드를 재귀적으로 추출

    Args:
        adf: ADF 형식 dict
        site_url: Atlassian 사이트 URL (첨부파일 URL 생성용)

    Returns:
        AdfMedia 리스트
    """
    media_list: list[AdfMedia] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            node_type = node.get("type")

            if node_type == "media":
                attrs = node.get("attrs", {})
                media_id = attrs.get("id", "")
                if media_id:
                    media_url = (
                        f"{site_url}/rest/api/3/attachment/content/{media_id}"
                        if site_url else None
                    )
                    media_list.append(AdfMedia(
                        id=media_id,
                        collection=attrs.get("collection"),
                        type=attrs.get("type"),
                        alt=attrs.get("alt"),
                        filename=attrs.get("__fileName"),
                        url=media_url,
                    ))

            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(adf.get("content", []))
    return media_list

