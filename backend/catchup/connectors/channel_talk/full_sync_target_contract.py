from __future__ import annotations

from catchup.utils.validation import require_text

CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET = "user_chat"
CHANNEL_TALK_USER_CHAT_DISPLAY_NAME = "UserChat"
CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET = "document_article"
CHANNEL_TALK_DOCUMENT_ARTICLE_DISPLAY_NAME = "DocumentArticle"
CHANNEL_TALK_CHANNEL_TARGET_KIND = "channel_talk.channel"
CHANNEL_TALK_DOCUMENT_SPACE_TARGET_KIND = "channel_talk.document_space"


def build_channel_talk_channel_metadata(
    channel_id: str,
) -> dict[str, str]:
    # Metadata는 설명/감사용이다. 실행 분기는 metadata가 아니라 target_type=channel이다.
    normalized_channel_id = require_text(channel_id, "channel_id")
    return {
        "target_kind": CHANNEL_TALK_CHANNEL_TARGET_KIND,
        "channel_id": normalized_channel_id,
    }


def build_channel_talk_document_space_metadata(
    channel_id: str,
) -> dict[str, str]:
    # space_id/space_name은 listing/resolver가 실제 Documents connection에서 채운다.
    # 이 함수는 공통으로 필요한 target_kind와 channel_id만 책임진다.
    normalized_channel_id = require_text(channel_id, "channel_id")
    return {
        "target_kind": CHANNEL_TALK_DOCUMENT_SPACE_TARGET_KIND,
        "channel_id": normalized_channel_id,
    }
