"""Custom retrieval tools for the Day 8 agents."""

from __future__ import annotations

from langchain_core.tools import tool

from Lab_Assigment.rag.retrieval import build_source_list, format_hits, retrieve_domain


def retrieve_legal_hits(query: str, top_k: int = 4) -> list[dict]:
    return retrieve_domain(query, "legal", top_k=top_k)


def retrieve_news_hits(query: str, top_k: int = 4) -> list[dict]:
    return retrieve_domain(query, "news", top_k=top_k)


@tool
def search_legal_kb(query: str, top_k: int = 4) -> str:
    """Search the legal corpus and return the most relevant evidence snippets."""
    return format_hits(retrieve_legal_hits(query, top_k=top_k))


@tool
def search_news_kb(query: str, top_k: int = 4) -> str:
    """Search the news corpus and return the most relevant evidence snippets."""
    return format_hits(retrieve_news_hits(query, top_k=top_k))


@tool
def list_source_labels(query: str, domain: str, top_k: int = 4) -> str:
    """Return normalized source labels for the selected domain."""
    hits = retrieve_domain(query, domain, top_k=top_k)
    labels = build_source_list(hits)
    return "\n".join(f"- {label}" for label in labels) if labels else "Không có nguồn trích dẫn."

