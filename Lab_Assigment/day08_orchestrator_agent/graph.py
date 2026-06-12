"""LangGraph orchestration for the Day 8 A2A legal RAG system."""

from __future__ import annotations

from collections import defaultdict, deque
import unicodedata
from typing import Annotated, TypedDict

from langgraph.constants import Send
from langgraph.graph import END, StateGraph

from Lab_Assigment.common.a2a_client import delegate
from Lab_Assigment.common.registry_client import discover
from Lab_Assigment.common.trace_store import append_trace
from Lab_Assigment.rag.synthesis import build_aggregate_answer, format_memory_context, parse_specialist_payload

MAX_DELEGATION_DEPTH = 3
MEMORY: dict[str, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=4))


def _last_wins(left: str, right: str) -> str:
    return right if right else left


class Day08OrchestratorState(TypedDict):
    question: str
    context_id: str
    trace_id: str
    delegation_depth: int
    memory_context: str
    needs_legal: bool
    needs_news: bool
    legal_result: Annotated[str, _last_wins]
    news_result: Annotated[str, _last_wins]
    final_answer: str


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def route_domains(question: str) -> tuple[bool, bool]:
    question_lower = _normalize_text(question)
    legal_keywords = [
        "luat", "nghi dinh", "bo luat", "trach nhiem", "hinh phat", "toi", "dieu", "ma tuy",
        "tai sao bi xu phat", "quy dinh", "cai nghien", "tang tru", "mua ban",
    ]
    news_keywords = [
        "tin tuc", "bao", "vnexpress", "vietnamnet", "nguoi mau", "ca si", "dien vien",
        "andrea", "huu tin", "chau viet cuong", "nghe si", "ban tin",
    ]

    needs_legal = any(keyword in question_lower for keyword in legal_keywords)
    needs_news = any(keyword in question_lower for keyword in news_keywords)

    if not needs_legal and not needs_news:
        needs_legal = True
    if needs_news and any(token in question_lower for token in ["hau qua", "xu phat", "toi danh", "trach nhiem"]):
        needs_legal = True
    return needs_legal, needs_news


def load_memory(state: Day08OrchestratorState) -> dict:
    append_trace(
        trace_id=state["trace_id"],
        stage="stage4",
        step="load_memory",
        agent="day08_orchestrator_agent",
        status="completed",
        detail="Nap bo nho hoi thoai gan day cho thread hien tai.",
        metadata={"context_id": state["context_id"]},
    )
    return {"memory_context": format_memory_context(MEMORY[state["context_id"]])}


def analyze_routing(state: Day08OrchestratorState) -> dict:
    depth = state.get("delegation_depth", 0)
    if depth >= MAX_DELEGATION_DEPTH:
        append_trace(
            trace_id=state["trace_id"],
            stage="stage4",
            step="analyze_routing",
            agent="day08_orchestrator_agent",
            status="completed",
            detail="Vuot qua max delegation depth, bo qua cac specialist.",
            metadata={"depth": depth},
        )
        return {"needs_legal": False, "needs_news": False}
    needs_legal, needs_news = route_domains(state["question"])
    append_trace(
        trace_id=state["trace_id"],
        stage="stage4",
        step="analyze_routing",
        agent="day08_orchestrator_agent",
        status="completed",
        detail=f"Phan tich routing: needs_legal={needs_legal}, needs_news={needs_news}",
    )
    return {"needs_legal": needs_legal, "needs_news": needs_news}


def route_to_agents(state: Day08OrchestratorState) -> list[Send]:
    sends: list[Send] = []
    if state.get("needs_legal"):
        sends.append(Send("call_legal_rag", state))
    if state.get("needs_news"):
        sends.append(Send("call_news_rag", state))
    if not sends:
        sends.append(Send("aggregate", state))
    append_trace(
        trace_id=state["trace_id"],
        stage="stage4",
        step="dispatch_specialists",
        agent="day08_orchestrator_agent",
        status="completed",
        detail="Xac dinh cac nhanh specialist can chay song song.",
        metadata={
            "needs_legal": bool(state.get("needs_legal")),
            "needs_news": bool(state.get("needs_news")),
            "fan_out": len(sends),
        },
    )
    return sends


async def call_legal_rag(state: Day08OrchestratorState) -> dict:
    try:
        endpoint = await discover("legal_kb_query")
        append_trace(
            trace_id=state["trace_id"],
            stage="stage5",
            step="discover_legal_rag",
            agent="day08_orchestrator_agent",
            status="completed",
            detail=f"Registry tra ve legal RAG endpoint {endpoint}",
        )
        result = await delegate(
            endpoint=endpoint,
            question=state["question"],
            context_id=state["context_id"],
            trace_id=state["trace_id"],
            depth=state.get("delegation_depth", 0) + 1,
        )
        append_trace(
            trace_id=state["trace_id"],
            stage="stage5",
            step="delegate_legal_rag",
            agent="day08_orchestrator_agent",
            status="completed",
            detail="Orchestrator da goi legal RAG agent va nhan ket qua.",
        )
        return {"legal_result": result}
    except Exception as exc:
        append_trace(
            trace_id=state["trace_id"],
            stage="stage5",
            step="delegate_legal_rag",
            agent="day08_orchestrator_agent",
            status="failed",
            detail=f"Khong goi duoc legal RAG: {exc}",
        )
        return {"legal_result": f'{{"domain":"legal","answer":"Legal RAG unavailable: {exc}","sources":[],"evidence":[]}}'}


async def call_news_rag(state: Day08OrchestratorState) -> dict:
    try:
        endpoint = await discover("news_kb_query")
        append_trace(
            trace_id=state["trace_id"],
            stage="stage5",
            step="discover_news_rag",
            agent="day08_orchestrator_agent",
            status="completed",
            detail=f"Registry tra ve news RAG endpoint {endpoint}",
        )
        result = await delegate(
            endpoint=endpoint,
            question=state["question"],
            context_id=state["context_id"],
            trace_id=state["trace_id"],
            depth=state.get("delegation_depth", 0) + 1,
        )
        append_trace(
            trace_id=state["trace_id"],
            stage="stage5",
            step="delegate_news_rag",
            agent="day08_orchestrator_agent",
            status="completed",
            detail="Orchestrator da goi news RAG agent va nhan ket qua.",
        )
        return {"news_result": result}
    except Exception as exc:
        append_trace(
            trace_id=state["trace_id"],
            stage="stage5",
            step="delegate_news_rag",
            agent="day08_orchestrator_agent",
            status="failed",
            detail=f"Khong goi duoc news RAG: {exc}",
        )
        return {"news_result": f'{{"domain":"news","answer":"News RAG unavailable: {exc}","sources":[],"evidence":[]}}'}


def aggregate(state: Day08OrchestratorState) -> dict:
    legal_payload = parse_specialist_payload(state.get("legal_result", ""), "legal") if state.get("legal_result") else None
    news_payload = parse_specialist_payload(state.get("news_result", ""), "news") if state.get("news_result") else None
    final_answer = build_aggregate_answer(
        question=state["question"],
        legal_payload=legal_payload,
        news_payload=news_payload,
        memory_context=state.get("memory_context", "Chua co lich su hoi thoai."),
    )
    append_trace(
        trace_id=state["trace_id"],
        stage="stage4",
        step="aggregate",
        agent="day08_orchestrator_agent",
        status="completed",
        detail="Tong hop phan tich legal/news thanh cau tra loi cuoi cung.",
        metadata={
            "has_legal_payload": legal_payload is not None,
            "has_news_payload": news_payload is not None,
        },
    )
    MEMORY[state["context_id"]].append({"question": state["question"], "answer": final_answer})
    return {"final_answer": final_answer}


def create_graph():
    graph = StateGraph(Day08OrchestratorState)
    graph.add_node("load_memory", load_memory)
    graph.add_node("analyze_routing", analyze_routing)
    graph.add_node("call_legal_rag", call_legal_rag)
    graph.add_node("call_news_rag", call_news_rag)
    graph.add_node("aggregate", aggregate)

    graph.set_entry_point("load_memory")
    graph.add_edge("load_memory", "analyze_routing")
    graph.add_conditional_edges(
        "analyze_routing",
        route_to_agents,
        ["call_legal_rag", "call_news_rag", "aggregate"],
    )
    graph.add_edge("call_legal_rag", "aggregate")
    graph.add_edge("call_news_rag", "aggregate")
    graph.add_edge("aggregate", END)
    return graph.compile()
