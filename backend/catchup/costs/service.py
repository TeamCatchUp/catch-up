from datetime import datetime
from datetime import timedelta
from typing import TypedDict

from catchup.costs.pricing import calc_token_cost
from catchup.db.costs import DailyModelTokenUsage


class DailyTokenCost(TypedDict):
    from_date: str
    to_date: str
    input_tokens: int
    output_tokens: int
    usd: float


class ChatTokenCostResult(TypedDict):
    total_usd: float
    daily_avg_usd: float
    by_date: list[DailyTokenCost]


def _generate_date_range(
    start: datetime, 
    end: datetime
) -> list[tuple[datetime, datetime]]:
    current = start
    dates = []
    while current < end:
        next_day = current + timedelta(days=1)
        dates.append((current, min(next_day, end)))
        current = next_day
    return dates


def _calculate_daily_cost(
    from_date: datetime,
    to_date: datetime,
    daily_model_usages: dict[str, DailyModelTokenUsage],
) -> DailyTokenCost:
    total_input = 0
    total_output = 0
    total_usd = 0.0

    for model_arn, usage in daily_model_usages.items():
        total_input += usage["input_tokens"]
        total_output += usage["output_tokens"]
        total_usd += calc_token_cost(
            model_arn,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
        )

    return {
        "from_date": from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to_date": to_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "usd": round(total_usd, 6),
        "input_tokens": total_input,
        "output_tokens": total_output,
    }


def calculate_chat_token_cost(
    usages: dict[int, dict[str, DailyModelTokenUsage]],
    start_date: datetime,
    end_date: datetime,
) -> ChatTokenCostResult:

    # date range별 토큰 사용량(USD) 계산
    by_date: list[DailyTokenCost] = []
    for i, (from_date, to_date) in enumerate(_generate_date_range(start_date, end_date)):
        by_date.append(_calculate_daily_cost(from_date, to_date, usages.get(i, {})))

    total_usd = round(sum(d["usd"] for d in by_date), 4)
    daily_avg_usd = round(total_usd / len(by_date), 4) if by_date else 0.0

    return {
        "total_usd": total_usd,
        "daily_avg_usd": daily_avg_usd,
        "by_date": by_date,
    }
