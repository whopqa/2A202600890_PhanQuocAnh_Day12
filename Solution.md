# Solution.md — Day 12: Deploy Your AI Agent to Production

> **Họ tên:** Phan Quoc Anh  
> **MSSV:** 2A202600890  
> **Ngày nộp:** 12/6/2026

---

## Part 1: Localhost vs Production

### Exercise 1.1 — 5 Anti-patterns trong `01-localhost-vs-production/develop/app.py`

| # | Vấn đề | Dòng code | Lý do nguy hiểm |
|---|--------|-----------|-----------------|
| 1 | **API key hardcode trong source code** | `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` | Nếu push lên GitHub, key bị lộ ngay lập tức, attacker có thể dùng để phát sinh chi phí hoặc lấy data |
| 2 | **Database URL với password hardcode** | `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` | Tương tự — credentials bị lộ trong version control history, không thể xoá hoàn toàn |
| 3 | **Debug mode bật trong production** | `reload=True` trong `uvicorn.run()` | Reload mode làm chậm app, tiêu tốn memory; debug mode có thể lộ stack trace cho client |
| 4 | **Port và host cố định (không đọc từ env)** | `host="localhost", port=8000` | `localhost` chỉ nhận kết nối nội bộ → container không nhận được traffic từ bên ngoài. Port cứng → xung đột khi Railway/Render inject `PORT` env var |
| 5 | **Logging bằng `print()` và log ra secret** | `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` | `print()` không có level/severity → không thể filter trong log aggregator. Quan trọng hơn: log ra API key — mọi người có access logs đều thấy key |
| 6 | **Không có `/health` endpoint** | *(thiếu hoàn toàn)* | Platform (Railway, Render, K8s) không biết container còn sống không → không thể tự động restart khi crash |

### Exercise 1.3 — Bảng so sánh Basic vs Advanced

| Feature | Basic (`develop/app.py`) | Advanced (`production/app.py`) | Tại sao quan trọng? |
|---------|--------------------------|-------------------------------|---------------------|
| **Config** | Hardcode trực tiếp trong code (`OPENAI_API_KEY = "sk-..."`) | Đọc từ environment variables qua `config.py` / `os.getenv()` | 12-Factor App: config phải tách khỏi code. Không bao giờ commit secrets lên Git |
| **Health check** | ❌ Không có | ✅ `GET /health` (liveness) + `GET /ready` (readiness) | Platform cần biết container có còn hoạt động không để tự động restart. Load balancer cần `/ready` để route traffic |
| **Logging** | `print()` — không có timestamp, level, format | Structured JSON logging (`{"time": "...", "level": "INFO", "msg": "..."}`) | JSON logs có thể parse, filter, aggregate bởi Datadog/Loki/CloudWatch. `print()` chỉ là text thuần |
| **Shutdown** | Đột ngột — process bị kill ngay | Graceful — `lifespan` context manager chờ request hiện tại hoàn thành trước khi đóng | Tránh mất request đang xử lý giữa chừng. Platform gửi SIGTERM trước SIGKILL 30 giây |
| **Port/Host** | `host="localhost"`, `port=8000` cứng | `host=settings.host` (mặc định `0.0.0.0`), `port=settings.port` từ `PORT` env | `0.0.0.0` để container nhận traffic từ Nginx/internet. Port từ env để Railway/Render inject |
| **Debug** | `reload=True` luôn bật | `reload=settings.debug` — chỉ bật khi `DEBUG=true` | Production không cần auto-reload, chỉ lãng phí resource và tiềm ẩn security risk |

---

## Part 2: Docker Containerization

### Exercise 2.1 — Phân tích `02-docker/develop/Dockerfile`

**1. Base image là gì?**  
```dockerfile
FROM python:3.11
```
Base image là `python:3.11` — full Python 3.11 distribution (~1 GB). Nặng vì bao gồm nhiều tools không cần thiết cho production.

**2. Working directory là gì?**  
```dockerfile
WORKDIR /app
```
Working directory là `/app` — tất cả lệnh tiếp theo (`COPY`, `RUN`, `CMD`) chạy trong thư mục này.

**3. Tại sao COPY requirements.txt trước khi COPY code?**  
```dockerfile
COPY 02-docker/develop/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY 02-docker/develop/app.py .
```
**Docker Layer Caching**: Mỗi instruction tạo một layer. Docker cache layer nếu files không đổi.  
- Nếu chỉ đổi `app.py` → Docker dùng cached layer của `pip install` → build **nhanh hơn nhiều** (tiết kiệm vài phút)  
- Nếu copy code và requirements cùng lúc → bất kỳ thay đổi code nào đều invalidate pip cache → phải cài lại toàn bộ dependencies

**4. CMD vs ENTRYPOINT khác nhau thế nào?**

| | `CMD` | `ENTRYPOINT` |
|--|-------|-------------|
| **Vai trò** | Default command — có thể override khi `docker run` | Fixed executable — không thể dễ override |
| **Override** | `docker run image python other.py` → override hoàn toàn | `docker run image --port 9000` → chỉ append arguments |
| **Dùng khi** | Muốn linh hoạt (dev/debug) | Muốn container luôn chạy 1 executable cụ thể |
| **Ví dụ** | `CMD ["python", "app.py"]` | `ENTRYPOINT ["uvicorn", "app:app"]` + `CMD ["--host", "0.0.0.0"]` |

**Best practice:** Dùng `ENTRYPOINT` cho executable chính + `CMD` cho default arguments.

### Exercise 2.3 — Multi-stage Build

**Stage 1 (builder) làm gì?**
```dockerfile
FROM python:3.11-slim AS builder
RUN apt-get install -y gcc libpq-dev  # build tools
RUN pip install --user -r requirements.txt  # install vào /root/.local
```
Cài đặt build tools (gcc, libpq-dev) và compile Python packages. Image này **không deploy**.

**Stage 2 (runtime) làm gì?**
```dockerfile
FROM python:3.11-slim AS runtime
COPY --from=builder /root/.local /app/.local  # copy packages đã compile
COPY app/ ./app/  # copy source code
USER agent  # non-root user
```
Chỉ copy những gì cần để **chạy** — không có pip, gcc, hay build tools.

**Tại sao image nhỏ hơn?**
- Builder stage có gcc (~100MB), build artifacts, pip cache — tất cả bị loại bỏ
- Runtime stage chỉ có: Python runtime + compiled packages + source code
- Kết quả: Basic (~1 GB) vs Advanced (~200-300 MB) → **~60-70% nhỏ hơn**

### Exercise 2.4 — Docker Compose Architecture

Services được start:
1. **redis** (7-alpine) — Cache, rate limiting, session storage
2. **agent** — FastAPI app (phụ thuộc redis healthy)  
3. **nginx** (1.27-alpine) — Reverse proxy, port 80

```
Internet
    │
    ▼
┌─────────────────────┐
│   Nginx :80         │  ← Public entry point
│   (Load Balancer)   │
└──────────┬──────────┘
           │  proxy_pass
           ▼
┌─────────────────────┐
│   Agent :8000       │  ← FastAPI app
│   (1-N replicas)    │
└──────────┬──────────┘
           │  redis://redis:6379
           ▼
┌─────────────────────┐
│   Redis :6379       │  ← Session, rate limit, history
└─────────────────────┘
```

Chúng communicate qua **Docker internal network** — tên service là hostname (`redis:6379`, `agent:8000`).

---

## Part 3: Cloud Deployment

### Exercise 3.2 — So sánh `render.yaml` vs `railway.toml`

| Tiêu chí | `render.yaml` | `railway.toml` |
|----------|--------------|----------------|
| **Format** | YAML — khai báo toàn bộ services | TOML — config build/deploy |
| **Scope** | Định nghĩa cả web service + Redis service trong 1 file | Chủ yếu define build command, start command |
| **Redis** | `type: redis` service riêng + link qua `fromService` | Thêm Redis riêng trong Railway dashboard hoặc qua plugin |
| **Secrets** | `generateValue: true` — Render auto-generate | Phải set bằng `railway variables set` |
| **Auto-deploy** | `autoDeploy: true` khi push Git | Mặc định auto-deploy |
| **Region** | `region: singapore` chỉ định được | Auto-select |

### Public URL (sau khi deploy)

> **API URL:** `https://ai-agent-production.onrender.com`  
> *(Cập nhật sau khi deploy thành công)*

**Test:**
```bash
# Health check
curl https://ai-agent-production.onrender.com/health

# Ask endpoint
curl https://ai-agent-production.onrender.com/ask \
  -X POST \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "student-01", "question": "What is Docker?"}'
```

---

## Part 4: API Security

### Exercise 4.1 — API Key Authentication (Basic)

**API key được check ở đâu?**
```python
# 04-api-gateway/develop/app.py
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key...")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key.")
    return api_key
```
Check ở **FastAPI dependency** — inject vào endpoint qua `Depends(verify_api_key)`.

**Điều gì xảy ra nếu sai key?**
- Không có key: `HTTP 401 Unauthorized` — "Missing API key"
- Sai key: `HTTP 403 Forbidden` — "Invalid API key"

**Làm sao rotate key?**
1. Set `AGENT_API_KEY=new-key` trong environment
2. Restart service
3. Thông báo clients cập nhật key
4. (Advanced) Implement key versioning — support cả old và new key trong grace period

### Exercise 4.2 — JWT Flow (Advanced)

```
Client                         Server
  │                               │
  │  POST /token                  │
  │  {username, password}  ──────►│ 1. Verify credentials
  │                               │ 2. Create JWT payload:
  │                               │    {sub: username, role, exp}
  │                               │ 3. Sign với SECRET_KEY (HS256)
  │◄─────── {access_token} ───────│
  │                               │
  │  POST /ask                    │
  │  Authorization: Bearer <token>│
  │  ─────────────────────────── ►│ 4. Extract token from header
  │                               │ 5. Verify signature với SECRET_KEY
  │                               │ 6. Check expiry (exp claim)
  │                               │ 7. Extract user_id, role
  │◄──── {answer: "..."}  ────────│
```

**Tại sao JWT?** Stateless — server không cần lưu session. Mỗi request tự verify được bằng chữ ký.

### Exercise 4.3 — Rate Limiting

**Algorithm:** `Sliding Window Counter` (production version dùng Redis Sorted Set)

```python
# 06-lab-complete/app/rate_limiter.py — Redis sliding window
pipe = redis_client.pipeline()
pipe.zremrangebyscore(key, 0, window_start)  # xoá requests cũ
pipe.zcard(key)                               # đếm requests còn lại trong window
_, request_count = pipe.execute()

if request_count >= settings.rate_limit_per_minute:
    raise HTTPException(429, ...)  # Too Many Requests
```

**Limit:** 10 requests/minute (mặc định) — cấu hình qua `RATE_LIMIT_PER_MINUTE` env var.

**Bypass limit cho admin?**  
```python
# 04-api-gateway/production/rate_limiter.py
rate_limiter_user = RateLimiter(max_requests=10, window_seconds=60)   # User
rate_limiter_admin = RateLimiter(max_requests=100, window_seconds=60) # Admin: 100 req/min
```
Admin dùng `rate_limiter_admin` — limit cao hơn 10x.

### Exercise 4.4 — Cost Guard Implementation

```python
# Giải pháp hoàn chỉnh
import redis
from datetime import datetime, timezone

r = redis.Redis()
MONTHLY_BUDGET_USD = 10.0
PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006

def check_budget(user_id: str, estimated_cost: float) -> bool:
    """
    Return True nếu còn budget, False nếu vượt.
    Logic:
    - Mỗi user có budget $10/tháng
    - Track spending trong Redis: key = "budget:{user_id}:{YYYY-MM}"
    - Reset tự động đầu tháng (key mới theo tháng)
    """
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    
    current = float(r.get(key) or 0)
    if current + estimated_cost > MONTHLY_BUDGET_USD:
        return False  # Vượt budget → HTTP 402 Payment Required
    
    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)  # 32 ngày TTL (qua tháng)
    return True
```

---

## Part 5: Scaling & Reliability

### Exercise 5.1 — Health Check Endpoints

```python
# Liveness probe — "Container còn sống không?"
@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# Readiness probe — "Sẵn sàng nhận traffic chưa?"
@app.get("/ready")
def ready():
    if not _ready:
        raise HTTPException(status_code=503, detail="Not ready")
    try:
        redis_client.ping()  # Check Redis connection
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Redis not ready") from exc
    return {"ready": True, "redis": "ok", "instance_id": INSTANCE_ID}
```

**Sự khác biệt quan trọng:**
- `/health` (Liveness): Luôn trả 200 nếu process còn sống → platform dùng để quyết định có restart không
- `/ready` (Readiness): Trả 503 nếu Redis chưa connect → load balancer dừng route traffic vào instance này

### Exercise 5.2 — Graceful Shutdown

```python
import signal

def shutdown_handler(signum, frame):
    """Handle SIGTERM từ container orchestrator"""
    logger.info("Received SIGTERM — initiating graceful shutdown")
    # uvicorn bắt SIGTERM tự động và gọi lifespan shutdown

signal.signal(signal.SIGTERM, shutdown_handler)

# Graceful shutdown qua FastAPI lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global _ready
    redis_client.ping()
    _ready = True
    
    yield  # App đang chạy
    
    # Shutdown — chạy khi nhận SIGTERM
    _ready = False           # Ngừng nhận traffic mới (readiness probe → 503)
    close_rate_limiter()     # Đóng Redis connections
    close_cost_guard()
    redis_client.close()
    logger.info("Shutdown complete")  # Graceful exit
```

**Flow khi Platform tắt container:**
1. Platform gửi `SIGTERM`
2. uvicorn dừng nhận request mới
3. Chờ in-flight requests hoàn thành (tối đa 30s: `stop_grace_period: 30s`)
4. Lifespan `finally` block đóng connections
5. Process exit

### Exercise 5.3 — Stateless Design

**Anti-pattern (state trong memory):**
```python
# ❌ Mỗi instance có memory riêng → scale ra nhiều instance thì mất history
conversation_history = {}

@app.post("/ask")
def ask(user_id: str, question: str):
    history = conversation_history.get(user_id, [])  # Chỉ thấy được nếu cùng instance!
    conversation_history[user_id].append(...)
```

**Đúng (state trong Redis):**
```python
# ✅ Redis là shared storage → mọi instance đều truy cập được cùng data
@app.post("/ask")
def ask(user_id: str, question: str):
    history = r.lrange(f"history:{user_id}", 0, -1)  # Load từ Redis
    r.rpush(f"history:{user_id}", new_message)        # Save vào Redis
```

**Tại sao stateless quan trọng?**  
Khi scale ra 3 instances, mỗi request từ user có thể đến bất kỳ instance nào. Nếu history lưu trong memory của instance A, user gửi request đến instance B sẽ mất toàn bộ lịch sử.

### Exercise 5.4 — Load Balancing với Nginx

```bash
docker compose up --scale agent=3
```

**Nginx upstream config (`nginx/default.conf`):**
```nginx
upstream agent_backend {
    server agent:8000;  # Docker DNS resolve sang tất cả replicas
}

server {
    listen 80;
    location / {
        proxy_pass http://agent_backend;
    }
}
```

Nginx dùng **Round Robin** (mặc định) — phân tán requests tuần tự giữa 3 instances.  
Nếu 1 instance die → Nginx detect healthcheck fail → stop routing đến instance đó → traffic tự chuyển sang 2 instances còn lại.

---

## Tổng Kết Production Checklist

| Tiêu chí | Điểm | Trạng thái |
|----------|------|-----------|
| Agent trả lời câu hỏi qua REST API | 20 | ✅ |
| Conversation history (Redis) | ✅ | ✅ |
| Multi-stage Dockerfile | 15 | ✅ |
| Config từ environment variables | ✅ | ✅ |
| API key authentication | 20 | ✅ |
| Rate limiting (10 req/min) | ✅ | ✅ |
| Cost guard ($10/month) | ✅ | ✅ |
| Health check endpoint | 20 | ✅ |
| Readiness check endpoint | ✅ | ✅ |
| Graceful shutdown | ✅ | ✅ |
| Stateless design (Redis) | 15 | ✅ |
| Structured JSON logging | ✅ | ✅ |
| Deploy lên Railway/Render | 10 | 🔄 Đang deploy |
| Public URL hoạt động | ✅ | 🔄 Đang deploy |

---

## Public API URL

> **Production URL:** `https://ai-agent-production.onrender.com`  
> *(Cập nhật sau khi deploy)*

**Test nhanh:**
```bash
curl https://ai-agent-production.onrender.com/health
```

**Expected response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production",
  "uptime_seconds": 42.1
}
```
