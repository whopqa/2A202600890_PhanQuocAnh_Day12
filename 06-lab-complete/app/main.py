"""Production-ready AI Agent for Day 12.

The application is intentionally stateless: conversation history, rate
windows, and budget usage live in Redis so multiple agent replicas can serve
the same user safely.
"""
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import close_cost_guard, record_usage
from app.rate_limiter import check_rate_limit, close_rate_limiter
from utils.mock_llm import ask as llm_ask


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(
    level=logging.DEBUG if settings.debug else getattr(logging, settings.log_level, logging.INFO),
    handlers=[handler],
    force=True,
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
INSTANCE_ID = settings.instance_id
_ready = False
_request_count = 0
_error_count = 0
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    history_turns: int
    served_by: str
    timestamp: str


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()) * 2)


def history_key(user_id: str) -> str:
    return f"history:{user_id}"


def load_history(user_id: str) -> list[dict]:
    raw_items = redis_client.lrange(history_key(user_id), 0, -1)
    history = []
    for item in raw_items:
        try:
            history.append(json.loads(item))
        except json.JSONDecodeError:
            logger.warning("Skipping invalid history item for user_id=%s", user_id)
    return history


def append_history(user_id: str, role: str, content: str) -> None:
    item = json.dumps(
        {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )
    key = history_key(user_id)
    pipe = redis_client.pipeline()
    pipe.rpush(key, item)
    pipe.ltrim(key, -settings.max_history_messages, -1)
    pipe.expire(key, settings.history_ttl_seconds)
    pipe.execute()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ready
    logger.info(
        json.dumps(
            {
                "event": "startup",
                "app": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
                "instance_id": INSTANCE_ID,
            },
            ensure_ascii=False,
        )
    )
    redis_client.ping()
    _ready = True
    logger.info(json.dumps({"event": "ready", "redis": "ok"}, ensure_ascii=False))
    try:
        yield
    finally:
        _ready = False
        close_rate_limiter()
        close_cost_guard()
        redis_client.close()
        logger.info(json.dumps({"event": "shutdown", "graceful": True}, ensure_ascii=False))


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
    except Exception:
        _error_count += 1
        logger.exception("Unhandled request error")
        raise

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    duration_ms = round((time.time() - start) * 1000, 1)
    logger.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "instance_id": INSTANCE_ID,
            },
            ensure_ascii=False,
        )
    )
    return response


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": INSTANCE_ID,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics (requires X-API-Key)",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
def ask_agent(body: AskRequest, request: Request, _api_key: str = Depends(verify_api_key)):
    check_rate_limit(body.user_id)

    history = load_history(body.user_id)
    input_tokens = estimate_tokens(body.question)
    record_usage(body.user_id, input_tokens=input_tokens, output_tokens=0)

    logger.info(
        json.dumps(
            {
                "event": "agent_call",
                "user_id": body.user_id,
                "question_length": len(body.question),
                "history_messages": len(history),
                "client": str(request.client.host) if request.client else "unknown",
            },
            ensure_ascii=False,
        )
    )

    append_history(body.user_id, "user", body.question)
    answer = llm_ask(body.question)
    output_tokens = estimate_tokens(answer)
    record_usage(body.user_id, input_tokens=0, output_tokens=output_tokens)
    append_history(body.user_id, "assistant", answer)

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        history_turns=(len(history) // 2) + 1,
        served_by=INSTANCE_ID,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/history/{user_id}", tags=["Agent"])
def get_history(user_id: str, _api_key: str = Depends(verify_api_key)):
    history = load_history(user_id)
    return {"user_id": user_id, "messages": history, "count": len(history)}


@app.get("/health", tags=["Operations"])
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _ready:
        raise HTTPException(status_code=503, detail="Not ready")
    try:
        redis_client.ping()
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Redis not ready") from exc
    return {"ready": True, "redis": "ok", "instance_id": INSTANCE_ID}


@app.get("/metrics", tags=["Operations"])
def metrics(_api_key: str = Depends(verify_api_key)):
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "instance_id": INSTANCE_ID,
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
