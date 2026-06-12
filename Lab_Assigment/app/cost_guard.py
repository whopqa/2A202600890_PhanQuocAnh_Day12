"""Monthly per-user LLM budget guard backed by Redis."""
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

try:
    from Lab_Assigment.app.config import settings
except ModuleNotFoundError:
    from app.config import settings  # type: ignore[no-redef]


PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1000 * PRICE_PER_1K_INPUT_TOKENS
        + output_tokens / 1000 * PRICE_PER_1K_OUTPUT_TOKENS
    )


def monthly_key(user_id: str) -> str:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    return f"budget:{user_id}:{month}"


def record_usage(user_id: str, input_tokens: int, output_tokens: int) -> dict:
    cost = estimate_cost(input_tokens, output_tokens)
    key = monthly_key(user_id)
    current = float(redis_client.get(key) or 0.0)

    if current + cost > settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(current, 6),
                "attempted_cost_usd": round(cost, 6),
                "budget_usd": settings.monthly_budget_usd,
            },
        )

    new_total = redis_client.incrbyfloat(key, cost)
    redis_client.expire(key, 32 * 24 * 3600)
    return {
        "user_id": user_id,
        "cost_usd": round(cost, 6),
        "monthly_total_usd": round(float(new_total), 6),
        "monthly_budget_usd": settings.monthly_budget_usd,
    }


def get_monthly_usage(user_id: str) -> dict:
    current = float(redis_client.get(monthly_key(user_id)) or 0.0)
    return {
        "user_id": user_id,
        "monthly_total_usd": round(current, 6),
        "monthly_budget_usd": settings.monthly_budget_usd,
        "remaining_usd": round(max(0.0, settings.monthly_budget_usd - current), 6),
    }


def close_cost_guard() -> None:
    redis_client.close()
