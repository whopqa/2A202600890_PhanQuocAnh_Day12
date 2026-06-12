# ============================================================
# Production Dockerfile — Multi-stage, non-root
# Legal RAG Multiagent System (Day 8 + Day 12)
# ============================================================

# ── Stage 1: Builder ─────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y \
        gcc libpq-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd -r agent && useradd -r -g agent -d /app agent

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /root/.local /app/.local

# ── Copy all application modules ─────────────────────────────
# Production middleware (FastAPI entrypoint + auth/rate/cost)
COPY app/               ./Lab_Assigment/app/
COPY utils/             ./Lab_Assigment/utils/

# RAG system modules
COPY common/            ./Lab_Assigment/common/
COPY rag/               ./Lab_Assigment/rag/
COPY src/               ./Lab_Assigment/src/

# Day08 agents
COPY day08_registry/            ./Lab_Assigment/day08_registry/
COPY day08_customer_agent/      ./Lab_Assigment/day08_customer_agent/
COPY day08_orchestrator_agent/  ./Lab_Assigment/day08_orchestrator_agent/
COPY day08_legal_rag_agent/     ./Lab_Assigment/day08_legal_rag_agent/
COPY day08_news_rag_agent/      ./Lab_Assigment/day08_news_rag_agent/
COPY day08_ui/                  ./Lab_Assigment/day08_ui/

# Data directory (vector store, chunks)
COPY data/              ./Lab_Assigment/data/

# Package init
COPY __init__.py        ./Lab_Assigment/__init__.py

# Ownership
RUN chown -R agent:agent /app

USER agent

ENV PATH=/app/.local/bin:$PATH
# PYTHONPATH=/app so that `import Lab_Assigment` resolves to /app/Lab_Assigment
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check — uses the FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

# Default: start FastAPI production middleware
# To start Day08 agents instead, override CMD in docker-compose
CMD ["sh", "-c", "uvicorn Lab_Assigment.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
