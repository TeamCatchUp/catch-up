from __future__ import annotations

from catchup.utils.validation import require_text

CHANNEL_TALK_BOOTSTRAP_TARGET_ID = "user_chat"
CHANNEL_TALK_BOOTSTRAP_DISPLAY_NAME = "UserChat"
CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID = "document_article"
CHANNEL_TALK_DOCUMENT_ARTICLE_DISPLAY_NAME = "DocumentArticle"


def build_channel_talk_bootstrap_metadata(
    channel_id: str,
) -> dict[str, str]:
    normalized_channel_id = require_text(channel_id, "channel_id")
    return {
        "runtime_target_kind": "bootstrap",
        "boundary": "tenant",
        "target": CHANNEL_TALK_BOOTSTRAP_TARGET_ID,
        "stage": CHANNEL_TALK_BOOTSTRAP_TARGET_ID,
        "channel_id": normalized_channel_id,
    }


def build_channel_talk_document_article_metadata(
    channel_id: str,
) -> dict[str, str]:
    normalized_channel_id = require_text(channel_id, "channel_id")
    return {
        "runtime_target_kind": "bootstrap",
        "boundary": "tenant",
        "target": CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
        "stage": CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
        "channel_id": normalized_channel_id,
    }
