"""Shared trace logging for the Day 8 distributed agent stack."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACE_DIR = Path(__file__).resolve().parent.parent / ".run" / "traces"


def _trace_path(trace_id: str) -> Path:
    safe_trace_id = "".join(char for char in trace_id if char.isalnum() or char in {"-", "_"})
    return TRACE_DIR / f"{safe_trace_id}.jsonl"


def clear_trace(trace_id: str) -> None:
    path = _trace_path(trace_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


def append_trace(
    trace_id: str,
    stage: str,
    step: str,
    agent: str,
    status: str,
    detail: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    path = _trace_path(trace_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "stage": stage,
        "step": step,
        "agent": agent,
        "status": status,
        "detail": detail,
        "metadata": metadata or {},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_trace(trace_id: str) -> list[dict[str, Any]]:
    path = _trace_path(trace_id)
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
    return events


def split_trace_by_stage(trace_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events = read_trace(trace_id)
    stage4 = [event for event in events if event.get("stage") == "stage4"]
    stage5 = [event for event in events if event.get("stage") == "stage5"]
    return stage4, stage5

