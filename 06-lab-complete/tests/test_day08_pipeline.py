from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from Lab_Assigment.day08_ui.app import app as ui_app
from Lab_Assigment.common.trace_store import append_trace, clear_trace
from Lab_Assigment.day08_orchestrator_agent.graph import route_domains
from Lab_Assigment.rag.retrieval import retrieve_domain
from Lab_Assigment.rag.synthesis import build_aggregate_answer


REPO_ROOT = Path(__file__).resolve().parents[2]


class RetrievalTests(unittest.TestCase):
    def test_legal_retrieval_filters_corpus(self) -> None:
        hits = retrieve_domain("hinh phat tang tru trai phep chat ma tuy", "legal", top_k=3)
        self.assertTrue(hits)
        for hit in hits:
            self.assertEqual(hit["metadata"].get("type"), "legal")
            self.assertIn("content", hit)
            self.assertIn("score", hit)
            self.assertIn("metadata", hit)
            self.assertIn("source", hit)

    def test_news_retrieval_filters_corpus(self) -> None:
        hits = retrieve_domain("Andrea Aybar va nghi van ma tuy", "news", top_k=3)
        self.assertTrue(hits)
        for hit in hits:
            self.assertEqual(hit["metadata"].get("type"), "news")


class RoutingTests(unittest.TestCase):
    def test_legal_only_question_routes_to_legal(self) -> None:
        self.assertEqual(route_domains("Dieu 249 Bo luat Hinh su quy dinh ra sao"), (True, False))

    def test_news_only_question_routes_to_news(self) -> None:
        self.assertEqual(route_domains("Bai bao nao noi ve Andrea Aybar"), (False, True))

    def test_mixed_question_routes_to_both(self) -> None:
        self.assertEqual(route_domains("Andrea Aybar co the bi xu phat theo quy dinh nao"), (True, True))

    def test_vietnamese_accented_question_routes_to_both(self) -> None:
        self.assertEqual(
            route_domains("Nghệ sĩ nào trong tin tức liên quan ma túy và hậu quả pháp lý là gì"),
            (True, True),
        )


class FallbackTests(unittest.TestCase):
    def test_fallback_aggregate_without_llm(self) -> None:
        os.environ["DAY08_DISABLE_LLM"] = "1"
        answer = build_aggregate_answer(
            question="Cau hoi thu nghiem",
            legal_payload={"answer": "Co so phap ly mau", "sources": ["luat.md, chunk 1"]},
            news_payload={"answer": "Tin tuc mau", "sources": ["article_01.md, chunk 2"]},
            memory_context="Chua co lich su hoi thoai.",
        )
        self.assertIn("Co so phap ly", answer)
        self.assertIn("Tin tuc", answer)
        self.assertIn("Luu y", answer)


class UiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(ui_app)

    def test_index_serves_html(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Day08 chatbot tu van phap ly", response.text)

    def test_chat_endpoint_returns_agent_payload(self) -> None:
        with patch(
            "Lab_Assigment.day08_ui.app.ask_customer_agent",
            new=AsyncMock(
                return_value={
                    "session_id": "demo-session",
                    "trace_id": "trace-123",
                    "answer": "Tra loi thu nghiem",
                    "latency_ms": 123,
                    "agent_endpoint": "http://127.0.0.1:11010",
                    "stage4_logs": [],
                    "stage5_logs": [],
                }
            ),
        ):
            response = self.client.post(
                "/api/chat",
                json={"question": "Hau qua phap ly la gi?", "session_id": "demo-session"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session_id"], "demo-session")
        self.assertIn("Tra loi thu nghiem", payload["answer"])
        self.assertEqual(payload["trace_id"], "trace-123")

    def test_status_endpoint_returns_service_rows(self) -> None:
        fake_statuses = [
            {
                "id": "customer",
                "name": "Customer Agent",
                "url": "http://127.0.0.1:11010/.well-known/agent.json",
                "healthy": True,
                "status_code": 200,
                "latency_ms": 19,
                "detail": None,
            }
        ]
        with patch(
            "Lab_Assigment.day08_ui.app.collect_service_statuses",
            new=AsyncMock(return_value=fake_statuses),
        ):
            response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], "customer")

    def test_runtime_endpoint_reports_openrouter(self) -> None:
        response = self.client.get("/api/runtime")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["ui_version"], "day08-ui-trace-v2")
        self.assertIn("OpenRouter", payload["provider"])
        self.assertIn("openrouter.ai", payload["api_base"])

    def test_trace_endpoint_returns_grouped_events(self) -> None:
        trace_id = "ui-trace-test"
        clear_trace(trace_id)
        append_trace(trace_id, "stage4", "aggregate", "day08_orchestrator_agent", "completed", "Tong hop xong.")
        append_trace(trace_id, "stage5", "customer_receive", "day08_customer_agent", "completed", "Da nhan.")
        response = self.client.get(f"/api/traces/{trace_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["trace_id"], trace_id)
        self.assertEqual(payload["stage4_logs"][0]["step"], "aggregate")
        self.assertEqual(payload["stage5_logs"][0]["step"], "customer_receive")


class IntegrationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        env = os.environ.copy()
        env["DAY08_REGISTRY_PORT"] = "12100"
        env["DAY08_CUSTOMER_AGENT_PORT"] = "12110"
        env["DAY08_ORCHESTRATOR_AGENT_PORT"] = "12111"
        env["DAY08_LEGAL_RAG_AGENT_PORT"] = "12112"
        env["DAY08_NEWS_RAG_AGENT_PORT"] = "12113"
        env["DAY08_UI_PORT"] = "12114"
        env["DAY08_REGISTRY_URL"] = "http://127.0.0.1:12100"
        env["DAY08_CUSTOMER_AGENT_URL"] = "http://127.0.0.1:12110"
        env["DAY08_ORCHESTRATOR_AGENT_URL"] = "http://127.0.0.1:12111"
        env["DAY08_LEGAL_RAG_AGENT_URL"] = "http://127.0.0.1:12112"
        env["DAY08_NEWS_RAG_AGENT_URL"] = "http://127.0.0.1:12113"
        env["DAY08_DISABLE_LLM"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        cls.env = env
        cls.processes = [
            subprocess.Popen([sys.executable, "-m", "Lab_Assigment.day08_registry"], cwd=REPO_ROOT, env=env),
            subprocess.Popen([sys.executable, "-m", "Lab_Assigment.day08_legal_rag_agent"], cwd=REPO_ROOT, env=env),
            subprocess.Popen([sys.executable, "-m", "Lab_Assigment.day08_news_rag_agent"], cwd=REPO_ROOT, env=env),
            subprocess.Popen([sys.executable, "-m", "Lab_Assigment.day08_orchestrator_agent"], cwd=REPO_ROOT, env=env),
            subprocess.Popen([sys.executable, "-m", "Lab_Assigment.day08_customer_agent"], cwd=REPO_ROOT, env=env),
            subprocess.Popen([sys.executable, "-m", "Lab_Assigment.day08_ui"], cwd=REPO_ROOT, env=env),
        ]
        cls._wait_for_url("http://127.0.0.1:12100/health", timeout=40)
        cls._wait_for_url("http://127.0.0.1:12112/.well-known/agent.json", timeout=40)
        cls._wait_for_url("http://127.0.0.1:12113/.well-known/agent.json", timeout=40)
        cls._wait_for_url("http://127.0.0.1:12111/.well-known/agent.json", timeout=40)
        cls._wait_for_url("http://127.0.0.1:12110/.well-known/agent.json", timeout=40)
        cls._wait_for_url("http://127.0.0.1:12114/health", timeout=40)

    @classmethod
    def tearDownClass(cls) -> None:
        for process in getattr(cls, "processes", []):
            process.terminate()
        for process in getattr(cls, "processes", []):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

    @staticmethod
    def _wait_for_url(url: str, timeout: int) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                response = httpx.get(url, timeout=3.0)
                if response.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError(f"Timed out waiting for {url}")

    def test_end_to_end_client(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "Lab_Assigment.test_client"],
            cwd=REPO_ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, msg=(result.stdout or "") + "\n" + (result.stderr or ""))
        self.assertIn("RESPONSE:", result.stdout)
        self.assertTrue("Co so phap ly" in result.stdout or "Cơ sở pháp lý" in result.stdout)

    def test_ui_status_endpoint(self) -> None:
        response = httpx.get("http://127.0.0.1:12114/api/status", timeout=10.0)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item["id"] == "customer" for item in payload))

    def test_ui_chat_returns_trace_logs(self) -> None:
        response = httpx.post(
            "http://127.0.0.1:12114/api/chat",
            json={
                "question": "Trong corpus co bai bao nao noi ve nghe si lien quan ma tuy va hau qua phap ly la gi?",
                "session_id": "integration-trace-session",
            },
            timeout=40.0,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["trace_id"])
        self.assertTrue(len(payload["stage5_logs"]) >= 3)
        self.assertTrue(any(item["step"] == "analyze_routing" for item in payload["stage4_logs"]))


if __name__ == "__main__":
    unittest.main()
