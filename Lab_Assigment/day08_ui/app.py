"""FastAPI app for the Day 8 chat UI."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from Lab_Assigment.common.a2a_client import delegate
from Lab_Assigment.common.llm import llm_enabled
from Lab_Assigment.common.trace_store import append_trace, clear_trace, split_trace_by_stage

STATIC_DIR = Path(__file__).resolve().parent / "static"
UI_BUILD_VERSION = "day08-ui-trace-v2"


def get_runtime_urls() -> dict[str, str]:
    return {
        "registry": os.getenv("DAY08_REGISTRY_URL", "http://127.0.0.1:11000"),
        "customer": os.getenv("DAY08_CUSTOMER_AGENT_URL", "http://127.0.0.1:11010"),
        "orchestrator": os.getenv("DAY08_ORCHESTRATOR_AGENT_URL", "http://127.0.0.1:11011"),
        "legal_rag": os.getenv("DAY08_LEGAL_RAG_AGENT_URL", "http://127.0.0.1:11012"),
        "news_rag": os.getenv("DAY08_NEWS_RAG_AGENT_URL", "http://127.0.0.1:11013"),
    }


def get_service_targets() -> list[tuple[str, str, str]]:
    urls = get_runtime_urls()
    return [
        ("registry", "Registry", f"{urls['registry']}/health"),
        ("customer", "Customer Agent", f"{urls['customer']}/.well-known/agent.json"),
        ("orchestrator", "Orchestrator Agent", f"{urls['orchestrator']}/.well-known/agent.json"),
        ("legal_rag", "Legal RAG Agent", f"{urls['legal_rag']}/.well-known/agent.json"),
        ("news_rag", "News RAG Agent", f"{urls['news_rag']}/.well-known/agent.json"),
    ]


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=200)


class ChatResponse(BaseModel):
    session_id: str
    trace_id: str
    answer: str
    latency_ms: int
    agent_endpoint: str
    stage4_logs: list["TraceEvent"]
    stage5_logs: list["TraceEvent"]


class ServiceStatus(BaseModel):
    id: str
    name: str
    url: str
    healthy: bool
    status_code: int | None = None
    latency_ms: int | None = None
    detail: str | None = None


class TraceEvent(BaseModel):
    timestamp: str
    trace_id: str
    stage: str
    step: str
    agent: str
    status: str
    detail: str
    metadata: dict[str, object] = Field(default_factory=dict)


class TraceResponse(BaseModel):
    trace_id: str
    stage4_logs: list[TraceEvent]
    stage5_logs: list[TraceEvent]


class RuntimeInfo(BaseModel):
    ui_version: str
    provider: str
    api_base: str
    model: str
    llm_enabled: bool
    disable_flag: bool


app = FastAPI(title="Day08 Legal RAG UI", version="1.0.0")
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR)), name="assets")


@app.middleware("http")
async def disable_browser_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


async def ask_customer_agent(question: str, session_id: str | None) -> ChatResponse:
    resolved_session_id = session_id or str(uuid4())
    customer_agent_url = get_runtime_urls()["customer"]
    trace_id = str(uuid4())
    clear_trace(trace_id)
    append_trace(
        trace_id=trace_id,
        stage="stage5",
        step="ui_submit",
        agent="day08_ui",
        status="completed",
        detail=f"UI gui cau hoi den customer agent {customer_agent_url}",
        metadata={"session_id": resolved_session_id},
    )
    started_at = time.perf_counter()
    answer = await delegate(
        endpoint=customer_agent_url,
        question=question.strip(),
        context_id=resolved_session_id,
        trace_id=trace_id,
        depth=0,
    )
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    if not answer:
        raise HTTPException(status_code=502, detail="Customer agent returned an empty response.")
    append_trace(
        trace_id=trace_id,
        stage="stage5",
        step="ui_receive_answer",
        agent="day08_ui",
        status="completed",
        detail="UI nhan cau tra loi cuoi cung tu customer agent.",
        metadata={"latency_ms": latency_ms},
    )
    stage4_logs, stage5_logs = split_trace_by_stage(trace_id)
    return ChatResponse(
        session_id=resolved_session_id,
        trace_id=trace_id,
        answer=answer,
        latency_ms=latency_ms,
        agent_endpoint=customer_agent_url,
        stage4_logs=[TraceEvent.model_validate(item) for item in stage4_logs],
        stage5_logs=[TraceEvent.model_validate(item) for item in stage5_logs],
    )


async def probe_service(
    http_client: httpx.AsyncClient,
    service_id: str,
    name: str,
    url: str,
) -> ServiceStatus:
    started_at = time.perf_counter()
    try:
        response = await http_client.get(url)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return ServiceStatus(
            id=service_id,
            name=name,
            url=url,
            healthy=response.status_code == 200,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return ServiceStatus(
            id=service_id,
            name=name,
            url=url,
            healthy=False,
            latency_ms=latency_ms,
            detail=str(exc),
        )


async def collect_service_statuses() -> list[ServiceStatus]:
    async with httpx.AsyncClient(timeout=4.0) as http_client:
        tasks = [
            probe_service(http_client=http_client, service_id=service_id, name=name, url=url)
            for service_id, name, url in get_service_targets()
        ]
        return await asyncio.gather(*tasks)


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status", response_model=list[ServiceStatus])
async def service_status() -> list[ServiceStatus]:
    return await collect_service_statuses()


@app.get("/api/runtime", response_model=RuntimeInfo)
async def runtime_info() -> RuntimeInfo:
    return RuntimeInfo(
        ui_version=UI_BUILD_VERSION,
        provider="OpenRouter via OpenAI-compatible ChatOpenAI",
        api_base="https://openrouter.ai/api/v1",
        model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-5"),
        llm_enabled=llm_enabled(),
        disable_flag=os.getenv("DAY08_DISABLE_LLM", "").lower() in {"1", "true", "yes"},
    )


@app.get("/api/traces/{trace_id}", response_model=TraceResponse)
async def trace_details(trace_id: str) -> TraceResponse:
    stage4_logs, stage5_logs = split_trace_by_stage(trace_id)
    return TraceResponse(
        trace_id=trace_id,
        stage4_logs=[TraceEvent.model_validate(item) for item in stage4_logs],
        stage5_logs=[TraceEvent.model_validate(item) for item in stage5_logs],
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be blank.")
    return await ask_customer_agent(question=request.question, session_id=request.session_id)
