"""Legal RAG specialist server for the Day 8 A2A runtime."""

from __future__ import annotations

import asyncio
import logging
import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from Lab_Assigment.common.registry_client import register
from Lab_Assigment.day08_legal_rag_agent.agent_executor import Day08LegalRagExecutor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [day08_legal_rag] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("DAY08_LEGAL_RAG_AGENT_PORT", "11012"))
AGENT_ENDPOINT = f"http://127.0.0.1:{PORT}"


async def _register_with_retry(max_attempts: int = 10, delay: float = 2.0) -> None:
    payload = {
        "agent_name": "day08-legal-rag-agent",
        "version": "1.0",
        "description": "Drug-law document retrieval specialist for the Day 8 legal chatbot.",
        "tasks": ["legal_kb_query"],
        "endpoint": AGENT_ENDPOINT,
        "tags": ["legal", "rag", "day08"],
    }
    for attempt in range(1, max_attempts + 1):
        try:
            await register(payload)
            logger.info("Registered with registry on attempt %d", attempt)
            return
        except Exception as exc:
            logger.warning("Registry not ready (%d/%d): %s", attempt, max_attempts, exc)
            await asyncio.sleep(delay)


async def main() -> None:
    await _register_with_retry()

    agent_card = AgentCard(
        name="Day08 Legal RAG Agent",
        description="Retrieve and summarize legal document evidence from the Day 8 corpus.",
        url=AGENT_ENDPOINT,
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="legal_kb_query",
                name="Legal KB Query",
                description="Search the Day08 legal document corpus and return grounded evidence.",
                tags=["legal", "rag", "kb"],
            )
        ],
    )

    executor = Day08LegalRagExecutor()
    request_handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore())
    app = A2AFastAPIApplication(agent_card=agent_card, http_handler=request_handler).build()

    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    logger.info("Day08 Legal RAG Agent listening on port %d", PORT)
    await uvicorn.Server(config).serve()


if __name__ == "__main__":
    asyncio.run(main())
