"""의도: connector 구조(Connector / Tenant boundary / Target stage 축)를 한곳에 모은다."""

from __future__ import annotations

from enum import StrEnum


class ConnectorKey(StrEnum):
    CHANNEL_TALK = "channel_talk"


class ConnectorBoundary(StrEnum):
    TENANT = "tenant"


class ConnectorStage(StrEnum):
    METADATA = "metadata"
    USER_CHAT_LIST = "user_chat_list"
    MESSAGE = "message"
