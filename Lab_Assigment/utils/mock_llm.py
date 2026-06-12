"""Offline mock LLM used by the final lab project."""
import random
import time


MOCK_RESPONSES = {
    "default": [
        "Day 12 agent is running with a mock LLM response.",
        "This production agent accepted your request and answered from the mock model.",
        "The agent is online, secured, rate limited, and ready for deployment.",
    ],
    "docker": ["Docker packages the app and dependencies so it runs the same everywhere."],
    "deploy": ["Deployment moves the agent from local development to a public cloud service."],
    "redis": ["Redis stores shared state so scaled agent replicas stay stateless."],
}


def ask(question: str, delay: float = 0.05) -> str:
    time.sleep(delay + random.uniform(0, 0.02))
    question_lower = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in question_lower:
            return random.choice(responses)
    return random.choice(MOCK_RESPONSES["default"])
