from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

CHANNEL_TALK_SEND_ACTION_ID = "channel_talk_send_guide_v1"
CHANNEL_TALK_SEND_MODAL_CALLBACK_ID = "channel_talk_send_guide_modal_v1"
CHANNEL_TALK_MESSAGE_MODE_BLOCK_ID = "channel_talk_message_mode"
CHANNEL_TALK_MESSAGE_MODE_ACTION_ID = "channel_talk_message_mode_select"
CHANNEL_TALK_MESSAGE_BLOCK_ID = "channel_talk_message"
CHANNEL_TALK_MESSAGE_ACTION_ID = "channel_talk_message_input"

_SLACK_MARKDOWN_TEXT_LIMIT = 12_000
_SLACK_PLAIN_TEXT_INPUT_LIMIT = 3_000


class ChannelTalkMessageMode(StrEnum):
    PRIVATE = "private"
    ACT_AS_MANAGER = "actAsManager"


@dataclass(slots=True, frozen=True)
class ChannelTalkActionPayload:
    channel_id: str
    user_chat_id: str


@dataclass(slots=True, frozen=True)
class ChannelTalkModalContext:
    channel_id: str
    user_chat_id: str
    slack_channel_id: str
    slack_user_id: str
    thread_ts: str | None


@dataclass(slots=True, frozen=True)
class ChannelTalkSubmission:
    mode: ChannelTalkMessageMode
    message: str


def build_guide_blocks(
    message: str,
    *,
    channel_id: str,
    user_chat_id: str,
) -> list[dict[str, Any]]:
    return [
        {
            "type": "markdown",
            "text": message[:_SLACK_MARKDOWN_TEXT_LIMIT],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": CHANNEL_TALK_SEND_ACTION_ID,
                    "text": {
                        "type": "plain_text",
                        "text": "채널톡으로 바로 전송하기",
                    },
                    "style": "primary",
                    "value": serialize_action_payload(
                        ChannelTalkActionPayload(
                            channel_id=channel_id,
                            user_chat_id=user_chat_id,
                        )
                    ),
                }
            ],
        },
    ]


def build_send_modal(
    context: ChannelTalkModalContext,
    *,
    draft: str,
) -> dict[str, Any]:
    return {
        "type": "modal",
        "callback_id": CHANNEL_TALK_SEND_MODAL_CALLBACK_ID,
        "private_metadata": serialize_modal_context(context),
        "title": {"type": "plain_text", "text": "채널톡으로 전송"},
        "submit": {"type": "plain_text", "text": "전송하기"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {
                "type": "input",
                "block_id": CHANNEL_TALK_MESSAGE_MODE_BLOCK_ID,
                "label": {"type": "plain_text", "text": "전송 방식"},
                "element": {
                    "type": "radio_buttons",
                    "action_id": CHANNEL_TALK_MESSAGE_MODE_ACTION_ID,
                    "options": [
                        _radio_option("내부대화", ChannelTalkMessageMode.PRIVATE),
                        _radio_option("고객 응대", ChannelTalkMessageMode.ACT_AS_MANAGER),
                    ],
                },
            },
            {
                "type": "input",
                "block_id": CHANNEL_TALK_MESSAGE_BLOCK_ID,
                "label": {"type": "plain_text", "text": "전송 내용"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": CHANNEL_TALK_MESSAGE_ACTION_ID,
                    "multiline": True,
                    "initial_value": draft[:_SLACK_PLAIN_TEXT_INPUT_LIMIT],
                },
            },
        ],
    }


def parse_action_payload(value: Any) -> ChannelTalkActionPayload | None:
    parsed = _parse_json_object(value)
    if parsed is None:
        return None
    channel_id = str(parsed.get("channel_id") or "").strip()
    user_chat_id = str(parsed.get("user_chat_id") or "").strip()
    if not channel_id or not user_chat_id:
        return None
    return ChannelTalkActionPayload(channel_id=channel_id, user_chat_id=user_chat_id)


def parse_modal_context(value: Any) -> ChannelTalkModalContext | None:
    parsed = _parse_json_object(value)
    if parsed is None:
        return None
    required = {
        key: str(parsed.get(key) or "").strip()
        for key in (
            "channel_id",
            "user_chat_id",
            "slack_channel_id",
            "slack_user_id",
        )
    }
    if not all(required.values()):
        return None
    return ChannelTalkModalContext(
        **required,
        thread_ts=str(parsed.get("thread_ts") or "").strip() or None,
    )


def parse_submission(payload: dict[str, Any]) -> ChannelTalkSubmission | None:
    values = payload.get("view", {}).get("state", {}).get("values", {})
    mode_value = (
        values.get(CHANNEL_TALK_MESSAGE_MODE_BLOCK_ID, {})
        .get(CHANNEL_TALK_MESSAGE_MODE_ACTION_ID, {})
        .get("selected_option", {})
        .get("value")
    )
    message = str(
        values.get(CHANNEL_TALK_MESSAGE_BLOCK_ID, {})
        .get(CHANNEL_TALK_MESSAGE_ACTION_ID, {})
        .get("value")
        or ""
    ).strip()
    try:
        mode = ChannelTalkMessageMode(str(mode_value or "").strip())
    except ValueError:
        return None
    if not message:
        return None
    return ChannelTalkSubmission(mode=mode, message=message)


def serialize_action_payload(payload: ChannelTalkActionPayload) -> str:
    return json.dumps(
        {"channel_id": payload.channel_id, "user_chat_id": payload.user_chat_id},
        separators=(",", ":"),
    )


def serialize_modal_context(context: ChannelTalkModalContext) -> str:
    return json.dumps(
        {
            "channel_id": context.channel_id,
            "user_chat_id": context.user_chat_id,
            "slack_channel_id": context.slack_channel_id,
            "slack_user_id": context.slack_user_id,
            "thread_ts": context.thread_ts,
        },
        separators=(",", ":"),
    )


def _radio_option(text: str, value: ChannelTalkMessageMode) -> dict[str, Any]:
    return {
        "text": {"type": "plain_text", "text": text},
        "value": value.value,
    }


def _parse_json_object(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
