from __future__ import annotations


def build_article_document_id(
    *,
    channel_id: str,
    space_id: str,
    language: str,
    article_id: str,
    chunk_index: int,
) -> str:
    # Deterministic ID: 같은 article/chunk는 항상 같은 id를 가져
    # 재동기화 시 vector DB의 replace/delete 기준으로 사용할 수 있다.
    return (
        "channel_talk:document_article:"
        f"{channel_id}:{space_id}:{language}:{article_id}:chunk:{chunk_index}"
    )


def build_article_delete_prefix(
    *,
    channel_id: str,
    space_id: str,
    language: str,
    article_id: str,
) -> str:
    # Prefix delete: article 하나에 속한 모든 chunk id가 공유하는 prefix다.
    # article 상태가 바뀌었을 때 기존 chunk 묶음을 한 번에 제거한다.
    return (
        "channel_talk:document_article:"
        f"{channel_id}:{space_id}:{language}:{article_id}:chunk:"
    )
