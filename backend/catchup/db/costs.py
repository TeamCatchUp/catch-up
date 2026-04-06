from datetime import datetime
from typing import TypedDict

from sqlalchemy import text
from sqlalchemy.orm import Session


class DailyModelTokenUsage(TypedDict):
    input_tokens: int
    output_tokens: int

type DailyTokenUsage = dict[str, dict[str, DailyModelTokenUsage]]

def get_user_chat_token_usage_by_range(
    db: Session,
    user_id: int,
    start_date: datetime,
    end_date: datetime,
) -> dict[int, dict[str, DailyModelTokenUsage]]:
    """start_date 기준 day_index별 모델별 토큰 사용량을 반환한다."""
    
    # start_date 기준 24시간 단위로 그룹화 (타임존과 무관)
    rows = db.execute(
        text("""
            SELECT
                FLOOR(EXTRACT(EPOCH FROM (created_at - :start_date)) / 86400)::int AS day_index,
                model_data.key AS model_id,
                COALESCE(SUM((model_data.value->>'input_tokens')::int), 0) AS input_tokens,
                COALESCE(SUM((model_data.value->>'output_tokens')::int), 0) AS output_tokens
            FROM chat_token_usages,
                 jsonb_each(token_breakdown) AS model_data
            WHERE user_id = :user_id
              AND created_at >= :start_date
              AND created_at < :end_date
            GROUP BY day_index, model_data.key
        """),
        {"user_id": user_id, "start_date": start_date, "end_date": end_date},
    ).all()

    result: dict[int, dict[str, DailyModelTokenUsage]] = {}
    for row in rows:
        if row.day_index not in result:
            result[row.day_index] = {}
        result[row.day_index][row.model_id] = {
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
        }
    return result


def get_org_chat_token_usage_by_range(
    db: Session,
    start_date: datetime,
    end_date: datetime,
) -> dict[int, dict[str, DailyModelTokenUsage]]:
    """start_date 기준 day_index별 조직 전체 토큰 사용량을 반환한다."""

    # start_date 기준 24시간 단위로 그룹화 (타임존과 무관)
    rows = db.execute(
        text("""
            SELECT
                FLOOR(EXTRACT(EPOCH FROM (created_at - :start_date)) / 86400)::int AS day_index,
                model_data.key AS model_id,
                COALESCE(SUM((model_data.value->>'input_tokens')::int), 0) AS input_tokens,
                COALESCE(SUM((model_data.value->>'output_tokens')::int), 0) AS output_tokens
            FROM chat_token_usages,
                 jsonb_each(token_breakdown) AS model_data
            WHERE created_at >= :start_date
              AND created_at < :end_date
            GROUP BY day_index, model_data.key
        """),
        {"start_date": start_date, "end_date": end_date},
    ).all()

    result: dict[int, dict[str, DailyModelTokenUsage]] = {}
    for row in rows:
        if row.day_index not in result:
            result[row.day_index] = {}
        result[row.day_index][row.model_id] = {
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
        }
    return result
