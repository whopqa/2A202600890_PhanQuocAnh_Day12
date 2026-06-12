"""End-to-end client for the Day 8 A2A legal RAG system."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from uuid import uuid4

import httpx
from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

DAY08_CUSTOMER_AGENT_URL = os.getenv("DAY08_CUSTOMER_AGENT_URL", "http://127.0.0.1:11010")
QUESTION = (
    "Theo quy định pháp luật hiện có, hậu quả pháp lý của việc tàng trữ trái phép chất ma túy là gì "
    "và có bài báo nào trong corpus nói về nghệ sĩ liên quan ma túy hay không?"
)


async def main() -> None:
    started_at = time.perf_counter()
    print(f"Connecting to Day08 Customer Agent at {DAY08_CUSTOMER_AGENT_URL}")
    print(f"Question: {QUESTION}")
    print("-" * 60)

    async with httpx.AsyncClient(timeout=300.0) as http_client:
        card_url = f"{DAY08_CUSTOMER_AGENT_URL}/.well-known/agent.json"
        try:
            card_resp = await http_client.get(card_url)
            card_resp.raise_for_status()
        except Exception as exc:
            print(f"ERROR: Could not reach Day08 Customer Agent at {card_url}")
            print(f"  {exc}")
            print("Make sure Day08 services are running (Lab_Assigment/start_all.ps1 or .sh)")
            sys.exit(1)

        from a2a.client import A2AClient
        from a2a.types import AgentCard, Message, Part, Role, SendMessageRequest, TextPart, MessageSendParams

        agent_card = AgentCard.model_validate(card_resp.json())
        print(f"Connected to agent: {agent_card.name} v{agent_card.version}")
        print("-" * 60)

        client = A2AClient(httpx_client=http_client, agent_card=agent_card)
        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=QUESTION))],
            message_id=str(uuid4()),
        )
        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(message=message),
        )

        print("Sending request...\n")
        response = await client.send_message(request)

        result_text = ""
        if hasattr(response, "root"):
            root = response.root
            if hasattr(root, "result"):
                result = root.result
                if hasattr(result, "artifacts") and result.artifacts:
                    for artifact in result.artifacts:
                        for part in artifact.parts:
                            inner = part.root if hasattr(part, "root") else part
                            if hasattr(inner, "text"):
                                result_text += inner.text
                elif hasattr(result, "parts") and result.parts:
                    for part in result.parts:
                        inner = part.root if hasattr(part, "root") else part
                        if hasattr(inner, "text"):
                            result_text += inner.text

        if result_text:
            elapsed = time.perf_counter() - started_at
            print("RESPONSE:")
            print("=" * 60)
            print(result_text)
            print("=" * 60)
            print(f"Latency: {elapsed:.2f}s")
        else:
            print("No text response received. Raw response:")
            print(response)


if __name__ == "__main__":
    asyncio.run(main())
