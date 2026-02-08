"""
Base Connector Utilities
"""

import re


def clean_markdown(text: str) -> str:
    """
    마크다운 텍스트 정리

    Args:
        text: 정리할 텍스트

    Returns:
        연속된 빈 줄이 제거된 텍스트
    """
    if not text:
        return ""
    # 연속된 빈 줄 제거 (3줄 이상 → 2줄)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_file_size(size: int) -> str:
    """
    파일 크기를 읽기 쉬운 형식으로 변환

    Args:
        size: 바이트 단위 크기

    Returns:
        포맷된 문자열 (예: "1.5 MB")
    """
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def make_document_id(source: str, entity_type: str, *identifiers: str | int) -> str:
    """
    Document ID 생성

    형식: {source}:{entity_type}:{id1}:{id2}:...

    Args:
        source: 데이터 소스 (github, jira, slack)
        entity_type: 엔티티 타입 (issue, pr, message 등)
        identifiers: 고유 식별자들

    Returns:
        Document ID 문자열

    Examples:
        "github:issue:owner/repo:123"
        "slack:message:C123:1234567890.123"
        "jira:issue:CAT-145"
    """
    parts = [source, entity_type] + [str(id_) for id_ in identifiers]
    return ":".join(parts)
