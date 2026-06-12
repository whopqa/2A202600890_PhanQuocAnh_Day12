"""Customer agent executor for the Day 8 A2A runtime."""

from __future__ import annotations

import logging
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, TextPart

from Lab_Assigment.common.a2a_client import delegate
from Lab_Assigment.common.registry_client import discover
from Lab_Assigment.common.trace_store import append_trace

logger = logging.getLogger(__name__)


class Day08CustomerAgentExecutor(AgentExecutor):
    """Front-door agent that forwards substantive questions to the orchestrator."""

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
            step="customer_receive",
            agent="day08_customer_agent",
            status="completed",
            detail="Customer agent nhan cau hoi tu UI hoac client.",
            metadata={"context_id": context_id, "depth": depth},
        )

        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.submit()
        await updater.start_work()

        try:
            endpoint = await discover("legal_consultation")
            append_trace(
                trace_id=trace_id,
                stage="stage5",
                step="customer_discover_orchestrator",
                agent="day08_customer_agent",
                status="completed",
                detail=f"Registry tra ve orchestrator endpoint {endpoint}",
            )
            answer = await delegate(
                endpoint=endpoint,
                question=question,
                context_id=context_id,
                trace_id=trace_id,
                depth=depth + 1,
            )
            append_trace(
                trace_id=trace_id,
                stage="stage5",
                step="customer_delegate_orchestrator",
                agent="day08_customer_agent",
                status="completed",
                detail="Customer agent da gui request sang orchestrator va nhan ket qua.",
            )
            if not answer:
                answer = "Khong nhan duoc phan hoi tu legal orchestrator."
            await updater.add_artifact(
                parts=[Part(root=TextPart(text=answer))],
                name="day08_customer_answer",
            )
            await updater.complete()
        except Exception as exc:
            append_trace(
                trace_id=trace_id,
                stage="stage5",
                step="customer_error",
                agent="day08_customer_agent",
                status="failed",
                detail=f"Customer agent loi: {exc}",
            )
            logger.exception("Day08 customer agent failed: %s", exc)
            await updater.failed(
                updater.new_agent_message(
                    parts=[Part(root=TextPart(text=f"Customer agent failed: {exc}"))]
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
