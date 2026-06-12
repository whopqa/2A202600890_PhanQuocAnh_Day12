"""Redis-backed sliding window rate limiter."""
import time

import redis
from fastapi import HTTPException

try:
    from Lab_Assigment.app.config import settings
except ModuleNotFoundError:
    from app.config import settings  # type: ignore[no-redef]


redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def check_rate_limit(user_id: str) -> dict:
    now = time.time()
    window_start = now - settings.rate_limit_window_seconds
    key = f"rate:{user_id}"

    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zcard(key)
    _, request_count = pipe.execute()

    if request_count >= settings.rate_limit_per_minute:
        oldest = redis_client.zrange(key, 0, 0, withscores=True)
        retry_after = settings.rate_limit_window_seconds
        if oldest:
            retry_after = max(1, int(oldest[0][1] + settings.rate_limit_window_seconds - now))
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": settings.rate_limit_per_minute,
                "window_seconds": settings.rate_limit_window_seconds,
                "retry_after_seconds": retry_after,
            },
            headers={
                "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(retry_after),
            },
        )

    member = f"{now}:{request_count}"
    pipe = redis_client.pipeline()
    pipe.zadd(key, {member: now})
    pipe.expire(key, settings.rate_limit_window_seconds)
    pipe.execute()

    remaining = settings.rate_limit_per_minute - request_count - 1
    return {
        "limit": settings.rate_limit_per_minute,
        "remaining": remaining,
        "window_seconds": settings.rate_limit_window_seconds,
    }


def close_rate_limiter() -> None:
    redis_client.close()
