#!/bin/bash
set -e

echo "Starting Day08 registry on port 11000..."
python -m Lab_Assigment.day08_registry &
REGISTRY_PID=$!
sleep 2

echo "Starting Day08 legal RAG agent on port 11012..."
python -m Lab_Assigment.day08_legal_rag_agent &
LEGAL_PID=$!

echo "Starting Day08 news RAG agent on port 11013..."
python -m Lab_Assigment.day08_news_rag_agent &
NEWS_PID=$!
sleep 3

echo "Starting Day08 orchestrator on port 11011..."
python -m Lab_Assigment.day08_orchestrator_agent &
ORCH_PID=$!
sleep 3

echo "Starting Day08 customer agent on port 11010..."
python -m Lab_Assigment.day08_customer_agent &
CUSTOMER_PID=$!

echo "Starting Day08 UI on port 11014..."
python -m Lab_Assigment.day08_ui &
UI_PID=$!

echo ""
echo "All Day08 services started:"
echo "  Registry:         http://127.0.0.1:11000"
echo "  Customer Agent:   http://127.0.0.1:11010"
echo "  Orchestrator:     http://127.0.0.1:11011"
echo "  Legal RAG:        http://127.0.0.1:11012"
echo "  News RAG:         http://127.0.0.1:11013"
echo "  Web UI:           http://127.0.0.1:11014"
echo ""
echo "Run Day08 client with:"
echo "  python -m Lab_Assigment.test_client"
echo ""
echo "Press Ctrl+C to stop all services."

wait $REGISTRY_PID $LEGAL_PID $NEWS_PID $ORCH_PID $CUSTOMER_PID $UI_PID
