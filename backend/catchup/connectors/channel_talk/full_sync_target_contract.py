from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from catchup.utils.validation import require_text

ChannelTalkPublicTargetType = Literal["channel", "space"]
ChannelTalkRuntimeTarget = Literal["user_chat", "document_article"]

CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET: ChannelTalkRuntimeTarget = "user_chat"
CHANNEL_TALK_USER_CHAT_DISPLAY_NAME = "UserChat"
CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET: ChannelTalkRuntimeTarget = (
    "document_article"
)
CHANNEL_TALK_DOCUMENT_ARTICLE_DISPLAY_NAME = "DocumentArticle"
CHANNEL_TALK_CHANNEL_TARGET_KIND = "channel_talk.channel"
CHANNEL_TALK_DOCUMENT_SPACE_TARGET_KIND = "channel_talk.document_space"


def _normalize_public_target_type(value: str) -> ChannelTalkPublicTargetType:
    target_type = require_text(value, "target_type")
    if target_type not in {"channel", "space"}:
        raise ValueError("target_type must be one of: channel, space")
    return target_type


def _normalize_runtime_target(value: str) -> ChannelTalkRuntimeTarget:
    runtime_target = require_text(value, "runtime_target")
    if runtime_target not in {"user_chat", "document_article"}:
        raise ValueError("runtime_target must be one of: user_chat, document_article")
    return runtime_target


@dataclass(frozen=True, slots=True)
class ChannelTalkFullSyncTargetPlan:
    target_type: ChannelTalkPublicTargetType
    target_id: str
    target_name: str
    runtime_target: ChannelTalkRuntimeTarget
    target_kind: str
    channel_id: str
    space_id: str | None = None
    space_name: str | None = None

    def __post_init__(self) -> None:
        target_type = _normalize_public_target_type(self.target_type)
        target_id = require_text(self.target_id, "target_id")
        target_name = require_text(self.target_name, "target_name")
        runtime_target = _normalize_runtime_target(self.runtime_target)
        target_kind = require_text(self.target_kind, "target_kind")
        channel_id = require_text(self.channel_id, "channel_id")

        object.__setattr__(self, "target_type", target_type)
        object.__setattr__(self, "target_id", target_id)
        object.__setattr__(self, "target_name", target_name)
        object.__setattr__(self, "runtime_target", runtime_target)
        object.__setattr__(self, "target_kind", target_kind)
        object.__setattr__(self, "channel_id", channel_id)

        if target_type == "channel":
            self._validate_channel_target(
                target_id=target_id,
                runtime_target=runtime_target,
                target_kind=target_kind,
                channel_id=channel_id,
            )
            return

        if target_type == "space":
            self._validate_document_space_target(
                target_id=target_id,
                runtime_target=runtime_target,
                target_kind=target_kind,
            )
            return

    @staticmethod
    def _validate_channel_target(
        *,
        target_id: str,
        runtime_target: ChannelTalkRuntimeTarget,
        target_kind: str,
        channel_id: str,
    ) -> None:
        if target_id != channel_id:
            raise ValueError("channel target_id must match channel_id")
        if runtime_target != CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET:
            raise ValueError("channel runtime_target must be user_chat")
        if target_kind != CHANNEL_TALK_CHANNEL_TARGET_KIND:
            raise ValueError("channel target_kind is invalid")

    def _validate_document_space_target(
        self,
        *,
        target_id: str,
        runtime_target: ChannelTalkRuntimeTarget,
        target_kind: str,
    ) -> None:
        raw_space_id = self.space_id
        raw_space_name = self.space_name
        if raw_space_id is None:
            raise ValueError("space_id is required")
        if raw_space_name is None:
            raise ValueError("space_name is required")

        space_id = require_text(raw_space_id, "space_id")
        space_name = require_text(raw_space_name, "space_name")
        object.__setattr__(self, "space_id", space_id)
        object.__setattr__(self, "space_name", space_name)

        if target_id != space_id:
            raise ValueError("space target_id must match space_id")
        if runtime_target != CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET:
            raise ValueError("space runtime_target must be document_article")
        if target_kind != CHANNEL_TALK_DOCUMENT_SPACE_TARGET_KIND:
            raise ValueError("space target_kind is invalid")

    @classmethod
    def channel(
        cls,
        *,
        channel_id: str,
        channel_name: str,
    ) -> "ChannelTalkFullSyncTargetPlan":
        normalized_channel_id = require_text(channel_id, "channel_id")
        return cls(
            target_type="channel",
            target_id=normalized_channel_id,
            target_name=require_text(channel_name, "channel_name"),
            runtime_target=CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET,
            target_kind=CHANNEL_TALK_CHANNEL_TARGET_KIND,
            channel_id=normalized_channel_id,
        )

    @classmethod
    def document_space(
        cls,
        *,
        channel_id: str,
        space_id: str,
        space_name: str,
    ) -> "ChannelTalkFullSyncTargetPlan":
        normalized_space_id = require_text(space_id, "space_id")
        normalized_space_name = require_text(space_name, "space_name")
        return cls(
            target_type="space",
            target_id=normalized_space_id,
            target_name=normalized_space_name,
            runtime_target=CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET,
            target_kind=CHANNEL_TALK_DOCUMENT_SPACE_TARGET_KIND,
            channel_id=require_text(channel_id, "channel_id"),
            space_id=normalized_space_id,
            space_name=normalized_space_name,
        )

    def to_metadata(self) -> dict[str, str]:
        metadata = {
            "target_kind": self.target_kind,
            "channel_id": self.channel_id,
        }
        if self.target_type == "space":
            raw_space_id = self.space_id
            raw_space_name = self.space_name
            if raw_space_id is None:
                raise ValueError("space_id is required")
            if raw_space_name is None:
                raise ValueError("space_name is required")
            metadata["space_id"] = require_text(raw_space_id, "space_id")
            metadata["space_name"] = require_text(raw_space_name, "space_name")
        return metadata

