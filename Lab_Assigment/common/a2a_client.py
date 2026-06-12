"""A2A delegation helper for the Day 8 runtime.

Compatible with a2a-sdk >= 0.2.0 (uses `create_client` / `Client` instead
of the deprecated `A2AClient`).
"""

from __future__ import annotations

import logging
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


async def delegate(
    endpoint: str,
    question: str,
    context_id: str,
    trace_id: str,
    depth: int,
) -> str:
    """Send a question to another A2A agent and return the text response."""
    try:
        # New a2a-sdk API (>= 0.2.0)
        from a2a.client import create_client
        from a2a.types import SendMessageRequest

        async with httpx.AsyncClient(timeout=120.0) as http_client:
            client = create_client(
                agent=endpoint,
                resolver_http_kwargs={"timeout": 30.0},
            )
            request = SendMessageRequest(
                message={
                    "role": "user",
                    "parts": [{"kind": "text", "text": question}],
                    "messageId": str(uuid4()),
                    "contextId": context_id,
                    "metadata": {
                        "trace_id": trace_id,
                        "context_id": context_id,
                        "delegation_depth": depth,
                    },
                }
            )
            logger.debug("Delegating to %s | trace=%s depth=%d", endpoint, trace_id, depth)
            full_text = []
            async for chunk in client.send_message(request):
                text = _extract_chunk_text(chunk)
                if text:
                    full_text.append(text)
            return "".join(full_text)

    except ImportError:
        # Fallback for older a2a-sdk (< 0.2.0) using A2AClient
        from a2a.client import A2AClient  # type: ignore[attr-defined]
        from a2a.types import AgentCard, Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart  # type: ignore[attr-defined]

        async with httpx.AsyncClient(timeout=120.0) as http_client:
            card_url = f"{endpoint}/.well-known/agent.json"
            card_resp = await http_client.get(card_url)
            card_resp.raise_for_status()
            agent_card = AgentCard.model_validate(card_resp.json())

            client = A2AClient(httpx_client=http_client, agent_card=agent_card)
            message = Message(
                role=Role.user,
                parts=[Part(root=TextPart(text=question))],
                message_id=str(uuid4()),
                context_id=context_id,
                metadata={
                    "trace_id": trace_id,
                    "context_id": context_id,
                    "delegation_depth": depth,
                },
            )
            request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=message),
            )
            logger.debug("Delegating to %s | trace=%s depth=%d", endpoint, trace_id, depth)
            response = await client.send_message(request)
            return _extract_text_legacy(response)


def _extract_chunk_text(chunk: object) -> str:
    """Extract text from a streaming chunk (new API)."""
    try:
        # StreamResponse → look for text parts
        result = getattr(chunk, "result", None)
        if result is None:
            return ""
        artifacts = getattr(result, "artifacts", None)
        if artifacts:
            texts = []
            for artifact in artifacts:
                for part in getattr(artifact, "parts", []) or []:
                    texts.append(_part_text(part))
            if texts:
                return "".join(texts)
        parts = getattr(result, "parts", None)
        if parts:
            return "".join(_part_text(p) for p in parts)
    except Exception:
        pass
    # If chunk itself has .text
    return getattr(chunk, "text", "") or ""


def _extract_text_legacy(response: object) -> str:
    """Extract text from old A2AClient response."""
    text = ""
    if hasattr(response, "root"):
        response = response.root

    result = getattr(response, "result", None)
    if result is None:
        return text

    artifacts = getattr(result, "artifacts", None)
    if artifacts:
        for artifact in artifacts:
            for part in getattr(artifact, "parts", []) or []:
                text += _part_text(part)
        if text:
            return text

    parts = getattr(result, "parts", None)
    if parts:
        for part in parts:
            text += _part_text(part)

    if not text:
        history = getattr(result, "history", None)
        if history:
            for message in history:
                for part in getattr(message, "parts", []) or []:
                    text += _part_text(part)
    return text


def _part_text(part: object) -> str:
    inner = getattr(part, "root", part)
    return getattr(inner, "text", "") or ""
