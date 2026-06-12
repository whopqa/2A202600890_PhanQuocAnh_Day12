"""News retrieval specialist service for the Day 8 A2A runtime."""

from __future__ import annotations

import json

from Lab_Assigment.rag.synthesis import build_specialist_response
from Lab_Assigment.common.trace_store import append_trace


def answer_question(question: str, trace_id: str | None = None) -> str:
    payload = build_specialist_response(question, domain="news", top_k=4)
    if trace_id:
        append_trace(
            trace_id=trace_id,
            stage="stage4",
            step="news_retrieval",
            agent="day08_news_rag_agent",
            status="completed",
            detail="News specialist da retrieval va tong hop bang chung.",
            metadata={
                "retrieval_mode": payload.get("retrieval_mode"),
                "source_count": len(payload.get("sources", [])),
                "top_source": payload.get("sources", [None])[0],
            },
        )
    return json.dumps(payload, ensure_ascii=False)
