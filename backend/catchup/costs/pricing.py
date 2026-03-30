# https://aws.amazon.com/bedrock/pricing/
# last updated at: 2026-03-30
# USD per token


TOKEN_PRICING: dict[str, dict[str, float]] = {
    "cohere.embed-v4": {
        "input": 0.12 / 1_000_000,
    },
    "claude-haiku-4-5": {
        "input": 1.0 / 1_000_000,
        "output": 5.0 / 1_000_000,
        "input_batch": 0.5 / 1_000_000,
        "output_batch": 2.5 / 1_000_000,
    },
}

QUERY_PRICING: dict[str, dict[str, float]] = {
    "cohere-rerank-3-5": {
        "per_query": 2.0 / 1_000,
    },
}


def calc_token_cost(
    model_id: str,
    input_tokens: int, 
    output_tokens: int = 0
) -> float:   
    pricing = TOKEN_PRICING[model_id]
    return (
        input_tokens * pricing.get("input", 0.0) +
        output_tokens * pricing.get("output", 0.0)
    )


def calc_query_cost(
    model_id: str,
    query_count: int
) -> float:
    pricing = QUERY_PRICING[model_id]
    return query_count * pricing["per_query"]