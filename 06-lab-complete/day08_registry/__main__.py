"""Registry service for the Day 8 A2A runtime."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [day08_registry] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)
PORT = int(os.getenv("DAY08_REGISTRY_PORT", "11000"))

app = FastAPI(title="Day08 A2A Registry", version="1.0.0")
agents: dict[str, dict[str, Any]] = {}


class AgentRegistration(BaseModel):
    agent_name: str
    version: str = "1.0"
    description: str = ""
    tasks: list[str] = []
    endpoint: str
    tags: list[str] = []


@app.post("/register", status_code=200)
async def register_agent(registration: AgentRegistration) -> dict[str, str]:
    entry = registration.model_dump()
    entry["registered_at"] = datetime.now(timezone.utc).isoformat()
    agents[registration.agent_name] = entry
    logger.info("Registered %s at %s", registration.agent_name, registration.endpoint)
    return {"status": "ok", "agent_name": registration.agent_name}


@app.get("/discover/{task}")
async def discover(task: str) -> dict[str, str]:
    for agent in agents.values():
        if task in agent.get("tasks", []):
            return {
                "agent_name": agent["agent_name"],
                "endpoint": agent["endpoint"],
                "description": agent.get("description", ""),
            }
    raise HTTPException(status_code=404, detail=f"No agent found for task '{task}'")


@app.get("/agents")
async def list_agents() -> dict[str, list[dict[str, Any]]]:
    return {"agents": list(agents.values())}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "agent_count": len(agents)}


if __name__ == "__main__":
    logger.info("Starting Day08 registry on port %d", PORT)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
