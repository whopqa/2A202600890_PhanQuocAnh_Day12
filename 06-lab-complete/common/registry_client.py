"""Registry client helpers for the Day 8 A2A runtime."""

from __future__ import annotations

import os

import httpx

DAY08_REGISTRY_URL = os.getenv("DAY08_REGISTRY_URL", "http://127.0.0.1:11000")


async def discover(task: str) -> str:
    """Return the endpoint URL of the agent that handles the given task."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{DAY08_REGISTRY_URL}/discover/{task}")
        response.raise_for_status()
        return response.json()["endpoint"]


async def register(agent_info: dict) -> None:
    """Register an agent with the Day 8 registry."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{DAY08_REGISTRY_URL}/register", json=agent_info)
        response.raise_for_status()

