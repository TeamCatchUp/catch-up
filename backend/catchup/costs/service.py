from typing import TypedDict

from catchup.components.aws.utils import extract_base_model_id_from_arn
from catchup.costs.pricing import calc_token_cost


class ModelTokenCost(TypedDict):
    input_tokens: int
    output_tokens: int
    usd: float


class ChatTokenCostResult(TypedDict):
    total_usd: float
    
    # key: base model id (e.g. "claude-sonnet-4-5")
    by_model: dict[str, ModelTokenCost] 


def _calculate_model_token_cost(
    model_arn: str,
    input_tokens: int,
    output_tokens: int,
) -> ModelTokenCost:
    usd = calc_token_cost(
        model_arn,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "usd": round(usd, 6),
    }


def calculate_chat_token_cost(
    usages: dict[str, dict[str, int]]
) -> ChatTokenCostResult:
    """
    모델별 토큰 사용량을 USD로 환산한다.

    Args:
        usages: get_user_chat_token_usages_by_model() 반환값
                e.g) {"arn:...haiku...": {"input_tokens": 1200, "output_tokens": 300}}

    Returns:
        합산 비용 및 모델별 breakdown
    """
    
    by_model: dict[str, ModelTokenCost] = {}
    for model_arn, breakdown in usages.items():
        base_model_id = extract_base_model_id_from_arn(model_arn)
        cost = _calculate_model_token_cost(model_arn, **breakdown)
        by_model[base_model_id] = cost
    
    total_usd = round(sum(m["usd"] for m in by_model.values()), 4)

    return {
        "total_usd": total_usd,
        "by_model": by_model,
    }