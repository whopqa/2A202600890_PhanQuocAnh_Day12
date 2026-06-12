# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

1. Hardcoded secrets in source code make leaked GitHub repos dangerous.
2. Fixed port values make the app harder to run on cloud platforms that inject `PORT`.
3. Debug behavior is tied to code instead of environment variables.
4. No health endpoint means the platform cannot tell whether the process is alive.
5. No readiness endpoint means traffic may be routed before dependencies are ready.
6. In-memory state disappears on restart and breaks when multiple replicas run.
7. Plain `print()` logging is harder to search and aggregate than structured logs.
8. No graceful shutdown can interrupt active requests during deploys or restarts.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config | Values are hardcoded | Values come from environment variables | Same code can run in local, staging, and cloud without edits |
| Secrets | Secret-like values can be committed | `.env.example` is committed, real `.env` is ignored | Prevents accidental credential leaks |
| Port | Fixed local port | Reads `PORT` from env | Required by Render, Railway, Cloud Run, and similar platforms |
| Health check | Missing or minimal | `GET /health` reports process status | Orchestrators can restart unhealthy containers |
| Readiness | Missing | `GET /ready` checks Redis | Load balancers only send traffic when dependencies are ready |
| Logging | Human-only print output | JSON structured logs | Easier debugging in cloud log dashboards |
| Shutdown | Abrupt process stop | Lifespan cleanup closes Redis clients | Safer deploys and cleaner resource release |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. Base image: `python:3.11-slim`, chosen because it is smaller than the full Python image but still easy to debug.
2. Working directory: `/app` in the runtime stage.
3. `COPY requirements.txt .` comes before copying application code so Docker can cache dependency installation when only code changes.
4. `CMD` provides the default command and can be overridden at runtime. `ENTRYPOINT` is more fixed and is usually used when the container should always behave like one executable.

### Exercise 2.3: Image size comparison

- Develop image: expected to be larger because a single-stage image often keeps build tools and extra layers.
- Production image: expected to be under 500 MB because it uses `python:3.11-slim` and a multi-stage build.
- Difference: multi-stage builds reduce the runtime image by copying only installed packages and application files, not compiler/build tooling.

### Exercise 2.4: Docker Compose architecture

```text
Client -> Nginx on localhost:8000 -> Agent replicas on port 8000 -> Redis
```

Services:

- `nginx`: public local entrypoint and load balancer.
- `agent`: FastAPI production agent.
- `redis`: shared state store for history, rate limits, and budget.

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

- Platform selected for this submission: Render.
- Railway remains supported conceptually through `railway.toml`.
- Public URL: fill in `DEPLOYMENT.md` after deploy.
- Screenshot: save deployment screenshots under `screenshots/`.

### Exercise 3.2: Render deployment

Render uses `render.yaml` as infrastructure-as-code. The final project defines:

- A Docker web service for the agent.
- A managed Redis service.
- `REDIS_URL` injected from the Redis service.
- Generated `AGENT_API_KEY` and `JWT_SECRET`.

Compared with Railway, Render blueprint files describe the web service and backing service together. Railway usually relies more on CLI/project variables.

### Exercise 3.3: Cloud Run notes

Cloud Run is more production-oriented and works well with CI/CD, but it requires more setup than Render/Railway. It is a good next step when the app needs stronger IAM, container registry, and autoscaling controls.

## Part 4: API Security

### Exercise 4.1: API key authentication

The final app verifies the `X-API-Key` header in `06-lab-complete/app/auth.py`.

Expected tests:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# Expected: 401

curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: local-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# Expected: 200
```

### Exercise 4.2: JWT authentication

The examples in `04-api-gateway/production` show JWT login and bearer token verification. The final project uses API key auth because the delivery checklist explicitly requires API key authentication for the production agent.

### Exercise 4.3: Rate limiting

The final app implements Redis sliding-window rate limiting in `06-lab-complete/app/rate_limiter.py`.

- Algorithm: sliding window using Redis sorted sets.
- Limit: 10 requests/minute/user.
- Result when exceeded: HTTP `429`.

### Exercise 4.4: Cost guard implementation

The final app implements a Redis monthly budget guard in `06-lab-complete/app/cost_guard.py`.

- Budget: 10 USD/month/user.
- Key shape: `budget:{user_id}:{YYYY-MM}`.
- Reset behavior: monthly key naturally changes each month, with a 32-day TTL.
- Result when exceeded: HTTP `402`.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health and readiness

- `/health`: returns process liveness without requiring Redis.
- `/ready`: checks Redis with `PING` and returns `503` if Redis is unavailable.

### Exercise 5.2: Graceful shutdown

The final app uses FastAPI lifespan cleanup to mark readiness false and close Redis clients during shutdown. Docker Compose sets `stop_grace_period: 30s`.

### Exercise 5.3: Stateless design

Conversation history, rate limit windows, and monthly budget usage are stored in Redis. The agent process does not rely on in-memory user state, so multiple replicas can serve the same user.

### Exercise 5.4: Load balancing

Docker Compose includes Nginx as the stable entrypoint. Run:

```bash
docker compose up --build --scale agent=3
```

Nginx forwards requests to the `agent` service replicas.

### Exercise 5.5: Stateless test

Test flow:

1. Send an authenticated `/ask` request with `user_id`.
2. Send another request with the same `user_id`.
3. Query `/history/{user_id}` and confirm both user and assistant messages are stored.
4. Restart an agent container and confirm the history remains available because it is stored in Redis.
