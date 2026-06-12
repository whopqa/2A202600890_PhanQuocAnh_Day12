"""Agent Render-ready for Lab 03.

Render injects the PORT environment variable at runtime, so the app must bind
to that value instead of a hardcoded local port.
"""
import os
import time
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Agent on Render", version="1.0.0")
START_TIME = time.time()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def mock_answer(question: str) -> str:
    question_lower = question.lower()
    if "render" in question_lower:
        return "Render deploys this FastAPI agent from render.yaml as infrastructure-as-code."
    if "cloud" in question_lower or "deploy" in question_lower:
        return "Cloud deployment gives the agent a public URL and managed runtime."
    return "This is a mock response from the Lab 03 Render-ready agent."


@app.get("/")
def root():
    return {
        "message": "AI Agent running on Render!",
        "docs": "/docs",
        "health": "/health",
    }


@app.post("/ask")
async def ask_agent(request: Request):
    body = await request.json()
    question = body.get("question", "")
    if not question:
        raise HTTPException(status_code=422, detail="question required")
    return {
        "question": question,
        "answer": mock_answer(question),
        "platform": "Render",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "platform": "Render",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
