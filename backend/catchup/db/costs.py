from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_user_chat_token_usage_by_model(
    db: Session,
    user_id: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, dict[str, int]]:
    """
    사용자의 모델별 채팅 토큰 사용량 합계를 반환한다.
    """
    conditions = ["user_id = :user_id"]
    params: dict = {"user_id": user_id}

    if start_date is not None:
        conditions.append("created_at >= :start_date")
        params["start_date"] = start_date
    if end_date is not None:
        conditions.append("created_at < :end_date")
        params["end_date"] = end_date

    where_clause = " AND ".join(conditions)

    rows = db.execute(
        text(f"""
            SELECT
                model_data.key AS model_id,
                COALESCE(SUM((model_data.value->>'input_tokens')::int), 0) AS input_tokens,
                COALESCE(SUM((model_data.value->>'output_tokens')::int), 0) AS output_tokens
            FROM chat_token_usages,
                 jsonb_each(token_breakdown) AS model_data
            WHERE {where_clause}
            GROUP BY model_data.key
        """),
        params,
    ).all()

    return {
        row.model_id: {
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
        }
        for row in rows
    }