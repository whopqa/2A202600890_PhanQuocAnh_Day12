# Day 12 Knowledge Explanation

This document explains what each required production concept means, where it appears in the repo, and how to verify it.

## 1. 12-Factor Configuration

Requirement: production behavior must be controlled by environment variables, not hardcoded values.

Implementation:

- `06-lab-complete/app/config.py` reads `PORT`, `REDIS_URL`, `AGENT_API_KEY`, `LOG_LEVEL`, `RATE_LIMIT_PER_MINUTE`, and `MONTHLY_BUDGET_USD`.
- `06-lab-complete/.env.example` documents the required variables without storing real secrets.

Role in repo: this allows the same codebase to run locally, in Docker Compose, and on Render.

Verify:

```bash
python 06-lab-complete/check_production_ready.py
```

## 2. Docker Multi-Stage Build

Requirement: package the app and dependencies into a reproducible container image under the lab size target.

Implementation:

- `06-lab-complete/Dockerfile` has a `builder` stage for installing dependencies.
- The `runtime` stage uses `python:3.11-slim`, copies only runtime artifacts, and runs as a non-root `agent` user.

Role in repo: Docker makes the runtime consistent between local testing and cloud deployment.

Verify:

```bash
cd 06-lab-complete
docker compose build
```

## 3. Cloud Deployment With Render

Requirement: provide a cloud deployment path with environment variables and a public URL.

Implementation:

- `06-lab-complete/render.yaml` defines the Docker web service.
- The same file defines a Render Redis service and injects its connection string into `REDIS_URL`.
- `DEPLOYMENT.md` records the public URL and test commands.

Role in repo: Render is the selected platform for turning the local agent into a public service.

Verify:

```bash
curl https://YOUR_RENDER_URL/health
```

## 4. API Key Authentication

Requirement: public endpoints must reject unauthenticated users.

Implementation:

- `06-lab-complete/app/auth.py` validates the `X-API-Key` header.
- `/ask`, `/history/{user_id}`, and `/metrics` depend on `verify_api_key`.

Role in repo: authentication protects the public agent from anonymous use.

Verify:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```

Expected result: `401`.

## 5. Rate Limiting

Requirement: limit each user to 10 requests per minute.

Implementation:

- `06-lab-complete/app/rate_limiter.py` uses a Redis sorted set per user.
- Old timestamps are removed, current requests are counted, and requests above the limit return `429`.

Role in repo: rate limiting protects the agent from accidental loops, abuse, and cost spikes.

Verify:

```bash
for /L %i in (1,1,15) do curl -X POST http://localhost:8000/ask -H "X-API-Key: local-secret-key" -H "Content-Type: application/json" -d "{\"user_id\":\"rate-test\",\"question\":\"hello\"}"
```

Expected result: later requests return `429`.

## 6. Cost Guard

Requirement: enforce a 10 USD monthly budget per user.

Implementation:

- `06-lab-complete/app/cost_guard.py` estimates token cost.
- Usage is stored in Redis keys like `budget:{user_id}:{YYYY-MM}`.
- Requests that would exceed the budget return `402`.

Role in repo: budget protection is essential for AI agents because model calls can become expensive.

Verify:

Temporarily set a very small `MONTHLY_BUDGET_USD` in `.env.local`, restart Compose, and call `/ask` until it returns `402`.

## 7. Health And Readiness

Requirement: expose endpoints that orchestrators can use to manage traffic and restarts.

Implementation:

- `GET /health` in `06-lab-complete/app/main.py` reports process liveness.
- `GET /ready` checks Redis and returns `503` if shared state is unavailable.

Role in repo: health checks support automatic recovery; readiness prevents routing traffic too early.

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## 8. Graceful Shutdown

Requirement: handle container shutdown cleanly.

Implementation:

- FastAPI lifespan in `06-lab-complete/app/main.py` marks the app not ready and closes Redis clients.
- `06-lab-complete/docker-compose.yml` sets `stop_grace_period: 30s`.

Role in repo: graceful shutdown makes deploys safer and prevents resource leaks.

Verify:

```bash
docker compose stop agent
docker compose logs agent
```

Look for the shutdown log with `"graceful": true`.

## 9. Stateless Redis Design

Requirement: do not store user state in process memory.

Implementation:

- Conversation history is stored in Redis list keys `history:{user_id}`.
- Rate limits and budget usage are also Redis-backed.
- Agent replicas can be scaled behind Nginx.

Role in repo: stateless app processes can scale horizontally and survive restarts.

Verify:

```bash
docker compose up --build --scale agent=3
curl -X POST http://localhost:8000/ask -H "X-API-Key: local-secret-key" -H "Content-Type: application/json" -d "{\"user_id\":\"stateless\",\"question\":\"Remember this\"}"
curl http://localhost:8000/history/stateless -H "X-API-Key: local-secret-key"
```
