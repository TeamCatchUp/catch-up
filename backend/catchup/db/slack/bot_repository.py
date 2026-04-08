import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import SlackChatThread


def get_slack_chat_thread(
    db: Session,
    *,
    team_id: str,
    channel_id: str,
    thread_ts: str,
) -> SlackChatThread | None:
    stmt = (
        select(SlackChatThread)
        .where(
            SlackChatThread.team_id == team_id,
            SlackChatThread.channel_id == channel_id,
            SlackChatThread.thread_ts == thread_ts,
        )
    )
    return db.scalar(stmt)


def create_slack_chat_thread(
    db: Session,
    *,
    team_id: str,
    channel_id: str,
    thread_ts: str,
    session_id: uuid.UUID,
    user_id: int,
    slack_user_id: str,
    last_raw_text: str | None,
) -> SlackChatThread:
    thread = SlackChatThread(
        team_id=team_id,
        channel_id=channel_id,
        thread_ts=thread_ts,
        session_id=session_id,
        user_id=user_id,
        slack_user_id=slack_user_id,
        last_raw_text=last_raw_text,
    )
    db.add(thread)
    db.flush()
    return thread


def touch_slack_chat_thread(
    thread: SlackChatThread,
    *,
    last_raw_text: str | None,
) -> SlackChatThread:
    thread.last_raw_text = last_raw_text
    return thread


def attach_chat_room(
    thread: SlackChatThread,
    *,
    chat_room_id: int,
) -> SlackChatThread:
    thread.chat_room_id = chat_room_id
    return thread
