import uuid
from datetime import datetime
from datetime import time
from datetime import timedelta
from typing import Optional

from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased
from sqlalchemy.orm import joinedload

from catchup.db.models import ChatHistory
from catchup.db.models import ChatRoom
from catchup.db.models import SenderType
from catchup.rag.schemas.sources import BaseSource


def get_chat_room(
    db: Session,
    session_id: uuid.UUID,
    user_id: int
) -> ChatRoom | None:
    """사용자 권한 확인을 포함한 세션 ID 기반 단일 채팅방 조회"""
    
    # 세션 ID 검증 및 사용자 권한 확인
    filter_query = (
        (ChatRoom.session_id == session_id) & 
        (ChatRoom.user_id == user_id)
    )
    
    return db.scalar(
        select(ChatRoom)
        .where(filter_query)
    )


def get_chat_rooms(
    db: Session,
    user_id: int,
    skip: int = 0,  # 앞에서 몇 개 건너뛸지
    limit: int = 20  # 몇 개 갸져올지
) -> tuple[list[ChatRoom], int]:  # (목록, 전체 개수)
    """채팅방 목록 조회"""
    
    filter_query = (ChatRoom.user_id == user_id)
    
    total_count = db.scalar(
        select(func.count())
        .select_from(ChatRoom)
        .where(filter_query)
    ) or 0
        
    stmt = (
        select(ChatRoom)
        .where(filter_query)
        .order_by(ChatRoom.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    items = db.scalars(stmt).all()
    
    return list(items), total_count


def create_chat_room(
    db: Session,
    session_id: uuid.UUID,
    user_id: int,
    workspace_id: int,
    title: str
) -> ChatRoom:
    """채팅방 생성"""
    room = ChatRoom(
        session_id=session_id,
        user_id=user_id,
        workspace_id=workspace_id,
        title=title
    )
    db.add(room)
    
    return room


def add_message(
    db: Session,
    room_id: int,
    role: str,
    content: str,
    sources: list[BaseSource] | None = None,
    trace_id: str | None = None 
) -> ChatHistory:
    """채팅 메시지 저장"""
    message = ChatHistory(
        chat_room_id=room_id,
        sender_type=SenderType.HUMAN if role == "user" else SenderType.ASSISTANT,
        content=content,
        sources=sources or [],
        trace_id=trace_id
    )
    db.add(message)
    
    return message


def get_chat_room_messages(
    db: Session,
    room_id: int,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[ChatHistory], int]:
    """채팅 메시지 히스토리 조회"""
    
    filter_query = (
        (ChatHistory.chat_room_id == room_id) &
        (ChatHistory.is_displayed == True)
    )
        
    total_count = db.scalar(
        select(func.count())
        .select_from(ChatHistory)
        .where(filter_query)
    ) or 0
    
    stmt = (
        select(ChatHistory)
        .where(filter_query)
        .order_by(ChatHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    items = db.scalars(stmt).all()
    
    return list(reversed(items)), total_count


def get_queries_by_user(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[ChatHistory], int]:
    
    """특정 사용자가 모든 채팅방에서 작성한 쿼리만 전체 조회 (최신 순)"""
    
    filter_query = (
        (ChatRoom.user_id == user_id) &
        (ChatHistory.sender_type == SenderType.HUMAN) &
        (ChatHistory.is_displayed == True)
    )
    
    total_count = db.scalar(
        select(func.count())
        .select_from(ChatHistory)
        .join(ChatRoom, ChatHistory.chat_room_id == ChatRoom.id)
        .where(filter_query)
    ) or 0
    
    stmt = (
        select(ChatHistory)
        .join(ChatRoom, ChatHistory.chat_room_id == ChatRoom.id)
        .options(joinedload(ChatHistory.chat_room))
        .where(filter_query)
        .order_by(ChatHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    items = db.scalars(stmt).all()
    
    return list(items), total_count


def get_queries_with_save_status(
    db: Session,
    user_id: Optional[int] = None,
    room_id: Optional[int] = None,
    search_term: Optional[str] = None,
    period: str = "all",
    is_saved: Optional[bool] = None,
    sort: str = "desc",
    skip: int = 0,
    limit: int = 20
) -> tuple[list[dict], int]:
    
    Answer = aliased(ChatHistory)
    
    is_saved_sq = (
        select(Answer.is_saved)
        .where(and_(
            Answer.chat_room_id == ChatHistory.chat_room_id,
            Answer.sender_type == SenderType.ASSISTANT,
            Answer.id > ChatHistory.id
        ))
        .order_by(Answer.id.asc()).limit(1).correlate(ChatHistory).scalar_subquery()
    )
    answer_id_sq = (
        select(Answer.id)
        .where(and_(
            Answer.chat_room_id == ChatHistory.chat_room_id,
            Answer.sender_type == SenderType.ASSISTANT,
            Answer.id > ChatHistory.id
        ))
        .order_by(Answer.id.asc()).limit(1).correlate(ChatHistory).scalar_subquery()
    )

    # 기본 필터
    filters = [ChatHistory.sender_type == SenderType.HUMAN, ChatHistory.is_displayed == True]
    if user_id:
        filters.append(ChatRoom.user_id == user_id)
    if room_id:
        filters.append(ChatHistory.chat_room_id == room_id)
        
    if period == "today":
        filters.append(ChatHistory.created_at >= datetime.combine(datetime.now().date(), time.min))
    elif period == "7d":
        filters.append(ChatHistory.created_at >= datetime.now() - timedelta(days=7))
    elif period == "30d":
        filters.append(ChatHistory.created_at >= datetime.now() - timedelta(days=30))
    
    # 검색 필터
    if search_term:
        filters.append(func.bigm_similarity(ChatHistory.content, search_term) > 0)
    if is_saved is True:
        filters.append(is_saved_sq == True)
    elif is_saved is False:
        # 답변이 명시적으로 False이거나, 아직 답변이 안 달려서 NULL인 경우를 모두 포함
        filters.append(or_(is_saved_sq == False, is_saved_sq.is_(None)))

    total_count = db.scalar(
        select(func.count()).select_from(ChatHistory).join(ChatRoom).where(and_(*filters))
    ) or 0

    stmt = (
        select(ChatHistory, is_saved_sq.label("is_answer_saved"), answer_id_sq.label("answer_id"))
        .join(ChatRoom)
        .options(joinedload(ChatHistory.chat_room))
        .where(and_(*filters))
    )

    # 정렬
    if search_term:
        stmt = stmt.order_by(func.bigm_similarity(ChatHistory.content, search_term).desc())
    else:
        stmt = stmt.order_by(ChatHistory.created_at.asc() if sort == "asc" else ChatHistory.created_at.desc())

    results = db.execute(stmt.offset(skip).limit(limit)).all()

    items = [{
        "id": r[0].id, "content": r[0].content, "created_at": r[0].created_at,
        "session_id": r[0].session_id, "is_answer_saved": r[1] or False, "answer_id": r[2]
    } for r in results]

    return items, total_count


def get_queries_by_user_with_save_status(db: Session, user_id: int, **kwargs):
    return get_queries_with_save_status(db, user_id=user_id, **kwargs)


def get_all_queries_for_admin(db: Session, **kwargs):
    return get_queries_with_save_status(db, **kwargs)


def get_queries_by_chat_room(
    db: Session,
    room_id: int,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[ChatHistory], int]:
    """특정 채팅방 내에서 사용자가 작성한 쿼리만 조회 (최신 순)"""
    filter_query = (
        (ChatHistory.chat_room_id == room_id) &
        (ChatHistory.sender_type == SenderType.HUMAN) &
        (ChatHistory.is_displayed == True)
    )
    
    total_count = db.scalar(
        select(func.count())
        .select_from(ChatHistory)
        .where(filter_query)
    ) or 0
    
    stmt = (
        select(ChatHistory)
        .where(filter_query)
        .order_by(ChatHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    items = db.scalars(stmt).all()
    
    return list(items), total_count


def get_message(
    db: Session,
    room_id: int,
    message_id: int
) -> ChatHistory:
    """단일 메세지 조회"""
    
    stmt = (
        select(ChatHistory)
        .where(
            (ChatHistory.id == message_id) &
            (ChatHistory.chat_room_id == room_id)
        )
    )
    return db.scalar(stmt)


def update_message_feedback(
    message: ChatHistory,
    is_liked: Optional[bool] = None,
    reasons: Optional[list[str]] = None,
    comment: Optional[str] = None,
) -> ChatHistory:
    message.is_liked = is_liked
    
    if is_liked is False:
        message.feedback_reasons = reasons
        message.feedback_comment = comment
    
    return message


def soft_delete_last_conversation_turn(
    db: Session,
    room_id: int
) -> Optional[str]:
    """
    특정 채팅방의 마지막 대화 턴을 soft-delete한다.
    사용자의 마지막 질문을 포함하여 이후 시점의 모든 메시지에 대해 
    is_displayed 속성을 False로 변경한다.
    사용자의 마지막 질문을 반환한다.
    """
    
    last_user_message = db.scalar(
        select(ChatHistory)
        .where(
            (ChatHistory.chat_room_id == room_id) &
            (ChatHistory.sender_type == SenderType.HUMAN) &
            (ChatHistory.is_displayed == True)
        )
        .order_by(ChatHistory.created_at.desc())
        .limit(1)
    )
    
    if not last_user_message:
        return None
    
    # sd: soft-deletion
    sd_target_messages = db.scalars(
        select(ChatHistory)
        .where(
            (ChatHistory.chat_room_id == room_id) &
            (ChatHistory.created_at >= last_user_message.created_at) &
            (ChatHistory.is_displayed == True)
        )
    ).all()
    
    for message in sd_target_messages:
        message.is_displayed = False  # soft-deletion 처리
        db.add(message)
        
    return last_user_message.content


def get_recent_messages(
    db: Session,
    session_id: uuid.UUID
) -> list[ChatHistory]:
    stmt = (
        select(ChatHistory)
        .join(ChatHistory.chat_room)
        .where(
            (ChatRoom.session_id == session_id) &
            (ChatHistory.is_displayed == True)
        )
        .order_by(ChatHistory.created_at.desc())
        .limit(20)  # 최근 10 턴의 대화
    )
    
    return db.scalars(stmt).all()


def toggle_save_status(
    db: Session,
    message: ChatHistory
) ->Optional[ChatHistory]:
    
    message = db.scalar(
        select(ChatHistory)
        .where(ChatHistory.id == message.id)
    )
    
    if not message:
        return None
    
    # save 상태 토글
    message.is_saved = not message.is_saved
    
    db.add(message)
    
    return message


def get_query_answer_pair(
    db: Session,
    message: ChatHistory
) -> list[ChatHistory]:
    """
    마이페이지 상세: 특정 사용자 질문과 그에 대응하는 바로 다음 AI 답변을 조회한다.
    """
    query = db.get(ChatHistory, message.id)
    if not query or query.sender_type != SenderType.HUMAN:
        return []

    answer = db.scalar(
        select(ChatHistory)
        .where(
            (ChatHistory.chat_room_id == query.chat_room_id) &
            (ChatHistory.sender_type == SenderType.ASSISTANT) &
            (ChatHistory.id > query.id)
        )
        .order_by(ChatHistory.id.asc())
        .limit(1)
    )

    return [query, answer] if answer else [query]


def get_user_message_with_ownership(
    db: Session,
    message_id: int, 
    user_id: int,
    is_admin: bool
) -> ChatHistory | None:
    """메시지 ID로 조회하되, 일반 유저라면 소유권을 확인하고 관리자라면 바로 반환"""
    
    stmt = select(ChatHistory).where(ChatHistory.id == message_id)
    
    if not is_admin:
        stmt = (
            stmt.join(ChatRoom, ChatHistory.chat_room_id == ChatRoom.id)
            .where(ChatRoom.user_id == user_id)
        )
        
    return db.scalar(stmt)


def get_user_question_count_by_range(
    db: Session,
    user_id: int,
    start_date: datetime,
    end_date: datetime,
) -> dict[int, int]:
    """start_date 기준 day_index별 유저의 질문 횟수를 반환한다."""
    rows = db.execute(
        text("""
            SELECT
                FLOOR(EXTRACT(EPOCH FROM (ch.created_at - :start_date)) / 86400)::int AS day_index,
                COUNT(*) AS question_count
            FROM chat_histories ch
            JOIN chat_rooms cr ON ch.chat_room_id = cr.id
            WHERE cr.user_id = :user_id
              AND ch.sender_type = 'human'
              AND ch.is_displayed = true
              AND ch.created_at >= :start_date
              AND ch.created_at < :end_date
            GROUP BY day_index
        """),
        {"user_id": user_id, "start_date": start_date, "end_date": end_date},
    ).all()

    return {row.day_index: row.question_count for row in rows}


def get_org_question_count_by_range(
    db: Session,
    start_date: datetime,
    end_date: datetime,
) -> dict[int, int]:
    """start_date 기준 day_index별 조직 전체 질문 횟수를 반환한다."""
    rows = db.execute(
        text("""
            SELECT
                FLOOR(EXTRACT(EPOCH FROM (created_at - :start_date)) / 86400)::int AS day_index,
                COUNT(*) AS question_count
            FROM chat_histories
            WHERE sender_type = 'human'
              AND is_displayed = true
              AND created_at >= :start_date
              AND created_at < :end_date
            GROUP BY day_index
        """),
        {"start_date": start_date, "end_date": end_date},
    ).all()

    return {row.day_index: row.question_count for row in rows}
