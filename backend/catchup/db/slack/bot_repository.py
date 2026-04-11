from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import uuid

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.db.models import SlackChatThread


@dataclass(slots=True, frozen=True)
class SlackThreadAcquireResult:
    outcome: str
    session_id: uuid.UUID | None = None
    lease_started_at: datetime | None = None
    reclaimed_stale: bool = False


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


def acquire_or_reject_slack_thread(
    db: Session,
    *,
    team_id: str,
    channel_id: str,
    thread_ts: str,
    user_id: int,
    slack_user_id: str,
    last_raw_text: str | None,
    now: datetime | None = None,
) -> SlackThreadAcquireResult:
    now_utc = _to_utc(now)
    inserted_session_id = uuid.uuid4()

    # 기존 이력이 없는 Slack 스레드 : row 생성과 lease 획득 동시 처리
    insert_stmt = (
        insert(SlackChatThread)
        .values(
            team_id=team_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            session_id=inserted_session_id,
            user_id=user_id,
            slack_user_id=slack_user_id,
            last_raw_text=last_raw_text,
            is_answer_in_progress=True,
            in_progress_started_at=now_utc,
        )
        .on_conflict_do_nothing(constraint="uq_slack_chat_threads_thread")
        .returning(
            SlackChatThread.session_id,
            SlackChatThread.in_progress_started_at,
        )
    )
    inserted = db.execute(insert_stmt).first()
    if inserted is not None:
        return SlackThreadAcquireResult(
            outcome="acquired",
            session_id=inserted.session_id,
            lease_started_at=inserted.in_progress_started_at,
        )

    # 이미 row가 있으면 해당 스레드를 잠근 뒤 재사용/회수/거절 여부를 판단
    thread = db.scalar(
        select(SlackChatThread)
        .where(
            SlackChatThread.team_id == team_id,
            SlackChatThread.channel_id == channel_id,
            SlackChatThread.thread_ts == thread_ts,
        )
        .with_for_update()
    )
    if thread is None:
        raise RuntimeError("slack chat thread disappeared during acquisition")

    # 다른 내부 사용자가 소유한 스레드면 기존 owner mismatch 흐름으로 거절
    if thread.user_id != user_id:
        return SlackThreadAcquireResult(outcome="owner_mismatch")

    # 같은 사용자의 활성 lease가 아직 유효하면 중복 실행을 막기 위해 busy를 반환
    if thread.is_answer_in_progress and not _is_stale_in_progress(thread, now_utc):
        return SlackThreadAcquireResult(
            outcome="busy",
            session_id=thread.session_id,
            lease_started_at=thread.in_progress_started_at,
        )

    # idle 또는 stale 상태면 기존 session을 유지한 채 lease를 다시 획득
    reclaimed_stale = thread.is_answer_in_progress
    thread.slack_user_id = slack_user_id
    thread.last_raw_text = last_raw_text
    thread.is_answer_in_progress = True
    thread.in_progress_started_at = now_utc
    db.flush()

    return SlackThreadAcquireResult(
        outcome="acquired",
        session_id=thread.session_id,
        lease_started_at=thread.in_progress_started_at,
        reclaimed_stale=reclaimed_stale,
    )


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


def release_slack_chat_thread(
    db: Session,
    *,
    team_id: str,
    channel_id: str,
    thread_ts: str,
    lease_started_at: datetime,
) -> bool:
    release_stmt = (
        update(SlackChatThread)
        .where(
            SlackChatThread.team_id == team_id,
            SlackChatThread.channel_id == channel_id,
            SlackChatThread.thread_ts == thread_ts,
            SlackChatThread.is_answer_in_progress.is_(True),
            SlackChatThread.in_progress_started_at == _to_utc(lease_started_at),
        )
        .values(
            is_answer_in_progress=False,
            in_progress_started_at=None,
        )
    )
    result = db.execute(release_stmt)
    db.flush()
    return bool(result.rowcount)


def _is_stale_in_progress(
    thread: SlackChatThread,
    now: datetime,
) -> bool:
    started_at = thread.in_progress_started_at
    if started_at is None:
        return True
    return now - _to_utc(started_at) >= timedelta(
        seconds=max(1, int(settings.SYNC_LOCK_CHANNEL_TTL_SECONDS)),
    )


def _to_utc(value: datetime | None) -> datetime:
    resolved = value or datetime.now(timezone.utc)
    if resolved.tzinfo is None:
        return resolved.replace(tzinfo=timezone.utc)
    return resolved.astimezone(timezone.utc)
