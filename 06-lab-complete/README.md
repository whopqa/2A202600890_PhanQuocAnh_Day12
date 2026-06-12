# Lab 12 - Complete Production Agent

This folder contains the final production-ready agent for Day 12. It combines the lab requirements into one deployable FastAPI service.

## What Is Included

- Multi-stage Dockerfile with a non-root runtime user
- Docker Compose stack with Nginx, scalable agent replicas, and Redis
- Render deployment blueprint with managed Redis
- API key authentication through `X-API-Key`
- Redis sliding-window rate limiting: 10 requests/minute/user
- Redis monthly cost guard: 10 USD/month/user
- Redis-backed conversation history
- `/health` liveness and `/ready` readiness endpoints
- Structured JSON logging and graceful shutdown cleanup
- Mock LLM, so no real OpenAI key is required for the lab

## Local Setup

```bash
cd 06-lab-complete
copy .env.example .env.local
```

Edit `.env.local` and set:

```env
AGENT_API_KEY=local-secret-key
JWT_SECRET=local-jwt-secret
```

## Run With Docker Compose

```bash
docker compose up --build
```

The Nginx entrypoint is available on:

```text
http://localhost:8000
```

## Test Commands

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Authentication should fail without a key:

```bash
curl -X POST http://localhost:8000/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"test\",\"question\":\"Hello\"}"
```

Authenticated request:

```bash
curl -X POST http://localhost:8000/ask ^
  -H "X-API-Key: local-secret-key" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"test\",\"question\":\"Hello\"}"
```

View conversation history:

```bash
curl http://localhost:8000/history/test -H "X-API-Key: local-secret-key"
```

## Scale Locally

```bash
docker compose up --build --scale agent=3
```

Nginx continues to expose one stable URL at `http://localhost:8000` while routing to the agent replicas.

## Production Readiness Check

```bash
python check_production_ready.py
```

## Render Deployment

1. Push this repository to GitHub.
2. In Render, choose **New > Blueprint**.
3. Select the repository and let Render read `06-lab-complete/render.yaml`.
4. Confirm generated secrets and deploy.
5. Test `/health`, `/ready`, and `/ask` using the commands in the root `DEPLOYMENT.md`.
