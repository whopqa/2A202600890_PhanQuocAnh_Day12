"""Legal RAG agent executor for the Day 8 A2A runtime."""

from __future__ import annotations

import logging
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, TextPart

from Lab_Assigment.day08_legal_rag_agent.service import answer_question
from Lab_Assigment.common.trace_store import append_trace

logger = logging.getLogger(__name__)


class Day08LegalRagExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        question = self._extract_question(context)
        context_id = context.context_id or str(uuid4())
        task_id = context.task_id or str(uuid4())
        metadata = context.message.metadata or {} if context.message else {}
        trace_id = metadata.get("trace_id", str(uuid4()))
        append_trace(
            trace_id=trace_id,
            stage="stage5",
            step="legal_rag_receive",
            agent="day08_legal_rag_agent",
            status="completed",
            detail="Legal RAG agent nhan request tu orchestrator.",
        )
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.submit()
        await updater.start_work()

        try:
            answer = answer_question(question, trace_id=trace_id)
            await updater.add_artifact(
                parts=[Part(root=TextPart(text=answer))],
                name="day08_legal_rag_answer",
            )
            await updater.complete()
        except Exception as exc:
            append_trace(
                trace_id=trace_id,
                stage="stage4",
                step="legal_retrieval",
                agent="day08_legal_rag_agent",
                status="failed",
                detail=f"Legal RAG loi: {exc}",
            )
            logger.exception("Day08 legal rag failed: %s", exc)
            await updater.failed(
                updater.new_agent_message(
                    parts=[Part(root=TextPart(text=f"Day08 legal rag failed: {exc}"))]
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
