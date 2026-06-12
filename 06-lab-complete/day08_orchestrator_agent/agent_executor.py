"""Orchestrator executor for the Day 8 A2A runtime."""

from __future__ import annotations

import logging
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, TextPart

from Lab_Assigment.common.trace_store import append_trace
from Lab_Assigment.day08_orchestrator_agent.graph import create_graph

logger = logging.getLogger(__name__)
_graph = create_graph()


class Day08OrchestratorExecutor(AgentExecutor):
    """Coordinate legal/news RAG sub-agents and synthesize the final answer."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        question = self._extract_question(context)
        context_id = context.context_id or str(uuid4())
        task_id = context.task_id or str(uuid4())
        metadata = context.message.metadata or {} if context.message else {}
        trace_id = metadata.get("trace_id", str(uuid4()))
        depth = int(metadata.get("delegation_depth", 0))
        append_trace(
            trace_id=trace_id,
            stage="stage5",
            step="orchestrator_receive",
            agent="day08_orchestrator_agent",
            status="completed",
            detail="Orchestrator nhan cau hoi va khoi tao state graph.",
            metadata={"context_id": context_id, "depth": depth},
        )

        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.submit()
        await updater.start_work()

        try:
            result = await _graph.ainvoke(
                {
                    "question": question,
                    "context_id": context_id,
                    "trace_id": trace_id,
                    "delegation_depth": depth,
                    "memory_context": "",
                    "needs_legal": False,
                    "needs_news": False,
                    "legal_result": "",
                    "news_result": "",
                    "final_answer": "",
                },
                config={"configurable": {"thread_id": context_id}},
            )
            answer = result.get("final_answer", "") or "Khong the tong hop cau tra loi luc nay."
            await updater.add_artifact(
                parts=[Part(root=TextPart(text=answer))],
                name="day08_orchestrated_answer",
            )
            await updater.complete()
            append_trace(
                trace_id=trace_id,
                stage="stage5",
                step="orchestrator_complete",
                agent="day08_orchestrator_agent",
                status="completed",
                detail="Orchestrator da tong hop xong cau tra loi cuoi cung.",
            )
        except Exception as exc:
            append_trace(
                trace_id=trace_id,
                stage="stage5",
                step="orchestrator_error",
                agent="day08_orchestrator_agent",
                status="failed",
                detail=f"Orchestrator loi: {exc}",
            )
            logger.exception("Day08 orchestrator failed: %s", exc)
            await updater.failed(
                updater.new_agent_message(
                    parts=[Part(root=TextPart(text=f"Day08 orchestrator failed: {exc}"))]
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id or str(uuid4()), context.context_id or str(uuid4()))
        await updater.cancel()

    @staticmethod
    def _extract_question(context: RequestContext) -> str:
        if context.message and context.message.parts:
            texts = []
            for part in context.message.parts:
                inner = getattr(part, "root", part)
                text = getattr(inner, "text", None)
                if text:
                    texts.append(text)
            return "\n".join(texts)
        return ""
