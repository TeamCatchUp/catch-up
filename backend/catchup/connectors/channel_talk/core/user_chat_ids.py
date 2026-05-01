from __future__ import annotations


def build_user_chat_document_id(
    *,
    channel_id: str,
    user_chat_id: str,
) -> str:
    return f"channel_talk:user_chat:{channel_id}:{user_chat_id}"


def build_user_chat_desk_url(
    *,
    channel_id: str,
    user_chat_id: str,
) -> str:
    return f"https://desk.channel.io/#/channels/{channel_id}/user_chats/{user_chat_id}"
