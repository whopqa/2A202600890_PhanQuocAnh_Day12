"""Production readiness checker for the Day 12 final project.

The output intentionally uses ASCII so it runs cleanly on Windows consoles.
"""
from pathlib import Path
import sys


BASE = Path(__file__).resolve().parent


def read(path: str) -> str:
    file_path = BASE / path
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


def check(name: str, passed: bool, detail: str = "") -> dict:
    status = "PASS" if passed else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")
    return {"name": name, "passed": passed}


def contains(path: str, *needles: str) -> bool:
    content = read(path).lower()
    return all(needle.lower() in content for needle in needles)


def run_checks() -> bool:
    results = []
    print("\n" + "=" * 58)
    print("  Production Readiness Check - Day 12 Lab")
    print("=" * 58)

    print("\nRequired files")
    required_files = [
        "Dockerfile",
        "docker-compose.yml",
        ".dockerignore",
        ".env.example",
        "requirements.txt",
        "render.yaml",
        "app/main.py",
        "app/config.py",
        "app/auth.py",
        "app/rate_limiter.py",
        "app/cost_guard.py",
        "utils/mock_llm.py",
    ]
    for file_name in required_files:
        results.append(check(f"{file_name} exists", (BASE / file_name).exists()))

    print("\nSecurity")
    gitignore = (BASE.parent / ".gitignore").read_text(encoding="utf-8")
    source = "\n".join(
        read(path)
        for path in [
            "app/main.py",
            "app/config.py",
            "app/auth.py",
            "app/rate_limiter.py",
            "app/cost_guard.py",
        ]
    )
    bad_secret_markers = ["sk-", "password123", "hardcoded"]
    found = [marker for marker in bad_secret_markers if marker in source.lower()]
    results.append(check(".env ignored by git", ".env" in gitignore))
    results.append(check("No obvious hardcoded secrets", not found, ", ".join(found)))
    results.append(check("API key auth implemented", contains("app/auth.py", "x-api-key", "401")))

    print("\nApplication behavior")
    results.append(check("/health endpoint defined", contains("app/main.py", '@app.get("/health"')))
    results.append(check("/ready endpoint checks Redis", contains("app/main.py", '@app.get("/ready"', "redis_client.ping")))
    results.append(check("/ask endpoint requires auth", contains("app/main.py", '@app.post("/ask"', "verify_api_key")))
    results.append(check("Redis-backed history", contains("app/main.py", "history:", "rpush", "ltrim")))
    results.append(check("Structured JSON logging", contains("app/main.py", "JSONFormatter", "json.dumps")))
    results.append(check("Graceful shutdown closes resources", contains("app/main.py", "finally:", "close_rate_limiter", "redis_client.close")))

    print("\nRate limit and budget")
    results.append(check("Redis sliding window rate limiter", contains("app/rate_limiter.py", "zadd", "zcard", "429")))
    results.append(check("Default limit is 10 req/min", contains("app/config.py", 'RATE_LIMIT_PER_MINUTE", "10"')))
    results.append(check("Monthly budget guard", contains("app/cost_guard.py", "budget:", "%y-%m", "402")))
    results.append(check("Default monthly budget is $10", contains("app/config.py", 'MONTHLY_BUDGET_USD", "10.0"')))

    print("\nDocker and deployment")
    dockerfile = read("Dockerfile")
    compose = read("docker-compose.yml")
    render = read("render.yaml")
    results.append(check("Multi-stage Dockerfile", " as builder" in dockerfile.lower() and " as runtime" in dockerfile.lower()))
    results.append(check("Non-root Docker user", "USER agent" in dockerfile))
    results.append(check("Docker healthcheck", "HEALTHCHECK" in dockerfile))
    results.append(check("Docker image uses slim base", "slim" in dockerfile.lower()))
    results.append(check("Compose has Redis", "redis:" in compose))
    results.append(check("Compose has Nginx load balancer", "nginx:" in compose and "agent_backend" in read("nginx/default.conf")))
    results.append(check("Render has Redis service", "type: redis" in render and "REDIS_URL" in render))

    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    pct = round(passed / total * 100)

    print("\n" + "=" * 58)
    print(f"  Result: {passed}/{total} checks passed ({pct}%)")
    if pct == 100:
        print("  PRODUCTION READY")
    elif pct >= 80:
        print("  Almost there. Fix the failed items above.")
    else:
        print("  Not ready yet. Review failed items above.")
    print("=" * 58 + "\n")
    return pct == 100


if __name__ == "__main__":
    sys.exit(0 if run_checks() else 1)
