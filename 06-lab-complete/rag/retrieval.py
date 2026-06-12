"""Day 8 retrieval adapter for filtered legal/news corpora."""

from __future__ import annotations

import json
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from Lab_Assigment.src.local_retrieval import corpus_idf, cosine_from_counters, expanded_tokens, get_chunks

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VECTOR_STORE_PATH = DATA_DIR / "vector_store.json"
VECTOR_EMBEDDINGS_PATH = DATA_DIR / "vector_store_embeddings.npy"
DEFAULT_TOP_K = 4
SCORE_THRESHOLD = 0.12


def _make_hit(entry: dict[str, Any], score: float, source: str) -> dict[str, Any]:
    return {
        "content": entry["content"],
        "score": float(score),
        "metadata": dict(entry.get("metadata", {})),
        "source": source,
    }


@lru_cache(maxsize=1)
def load_vector_store() -> tuple[dict[str, Any], ...]:
    if not VECTOR_STORE_PATH.exists():
        return tuple()
    return tuple(json.loads(VECTOR_STORE_PATH.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def load_vector_embeddings():
    if not VECTOR_EMBEDDINGS_PATH.exists():
        return None
    try:
        import numpy as np
    except Exception:
        return None
    return np.load(VECTOR_EMBEDDINGS_PATH)


def domain_entries(domain: str) -> list[tuple[int, dict[str, Any]]]:
    entries = []
    for index, entry in enumerate(load_vector_store()):
        if entry.get("metadata", {}).get("type") == domain:
            entries.append((index, entry))
    return entries


def source_label(hit: dict[str, Any]) -> str:
    metadata = hit.get("metadata", {})
    source = metadata.get("source", "unknown")
    chunk_index = metadata.get("chunk_index", "?")
    return f"{source}, chunk {chunk_index}"


def format_hits(hits: list[dict[str, Any]], max_excerpt: int = 220) -> str:
    if not hits:
        return "Không tìm thấy trích đoạn liên quan."
    lines = []
    for hit in hits:
        excerpt = " ".join(hit["content"].split())
        if len(excerpt) > max_excerpt:
            excerpt = f"{excerpt[:max_excerpt].rstrip()}..."
        lines.append(f"- [{source_label(hit)}] {excerpt}")
    return "\n".join(lines)


def semantic_search_domain(query: str, domain: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
    except Exception:
        return []

    entries = domain_entries(domain)
    if not entries:
        return []

    embeddings = load_vector_embeddings()
    if embeddings is None:
        return []

    if not hasattr(semantic_search_domain, "_model"):
        semantic_search_domain._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    query_embedding = semantic_search_domain._model.encode([query])[0]
    query_norm = np.linalg.norm(query_embedding)
    if query_norm == 0:
        return []

    indices = [index for index, _ in entries]
    domain_embeddings = embeddings[indices]
    embedding_norms = np.linalg.norm(domain_embeddings, axis=1)
    scores = np.dot(domain_embeddings, query_embedding) / (embedding_norms * query_norm + 1e-12)
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for local_rank in top_indices:
        entry = entries[int(local_rank)][1]
        results.append(_make_hit(entry, float(scores[local_rank]), "semantic"))
    return results


def lexical_search_domain(query: str, domain: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    entries = domain_entries(domain)
    if not entries:
        return []

    try:
        from rank_bm25 import BM25Okapi
    except Exception:
        return deterministic_search_domain(query, domain, top_k)

    cache_key = f"_{domain}_bm25"
    if not hasattr(lexical_search_domain, cache_key):
        corpus = [entry["content"].lower().split() for _, entry in entries]
        setattr(lexical_search_domain, cache_key, BM25Okapi(corpus))

    bm25 = getattr(lexical_search_domain, cache_key)
    query_tokens = query.lower().split()
    scores = bm25.get_scores(query_tokens)

    try:
        import numpy as np
    except Exception:
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:top_k]
    else:
        ranked = [(int(idx), float(scores[idx])) for idx in np.argsort(scores)[::-1][:top_k]]

    results = []
    for position, score in ranked:
        if score <= 0:
            continue
        entry = entries[position][1]
        results.append(_make_hit(entry, float(score), "lexical"))
    return results


def deterministic_search_domain(query: str, domain: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    query_counter = Counter(expanded_tokens(query))
    chunks = [
        chunk for chunk in get_chunks()
        if chunk.get("metadata", {}).get("type") == domain
    ]
    if not chunks:
        return []

    tokenized_docs = [expanded_tokens(chunk["content"]) for chunk in chunks]
    idf = corpus_idf(tokenized_docs)
    scored = []
    for chunk, tokens in zip(chunks, tokenized_docs):
        score = cosine_from_counters(query_counter, Counter(tokens), idf=idf)
        if score > 0:
            scored.append(_make_hit(chunk, score, "offline-local"))
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def merge_ranked_lists(ranked_lists: list[list[dict[str, Any]]], top_k: int) -> list[dict[str, Any]]:
    try:
        from Lab_Assigment.src.task7_reranking import rerank_rrf
    except Exception:
        rerank_rrf = None

    if rerank_rrf is not None:
        merged = rerank_rrf(ranked_lists, top_k=top_k)
    else:
        aggregated: dict[str, dict[str, Any]] = {}
        for ranked_list in ranked_lists:
            for rank, item in enumerate(ranked_list, start=1):
                key = f"{item['metadata'].get('source')}#{item['metadata'].get('chunk_index')}"
                fused_score = 1.0 / (60 + rank)
                if key not in aggregated:
                    aggregated[key] = dict(item)
                    aggregated[key]["score"] = fused_score
                else:
                    aggregated[key]["score"] += fused_score
        merged = sorted(aggregated.values(), key=lambda item: item["score"], reverse=True)[:top_k]

    for item in merged:
        item["source"] = "hybrid"
    return merged


def rerank_candidates(query: str, candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    try:
        from Lab_Assigment.src.task7_reranking import rerank
    except Exception:
        rerank = None

    if rerank is None:
        return candidates[:top_k]

    try:
        return rerank(query, candidates, top_k=top_k, method="cross_encoder")
    except Exception:
        return candidates[:top_k]


def retrieve_domain(query: str, domain: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    dense_hits = semantic_search_domain(query, domain, top_k=top_k * 2)
    sparse_hits = lexical_search_domain(query, domain, top_k=top_k * 2)
    local_hits = deterministic_search_domain(query, domain, top_k=top_k * 2)

    hybrid_candidates = merge_ranked_lists(
        [hits for hits in [dense_hits, sparse_hits, local_hits] if hits],
        top_k=top_k * 2,
    ) if any([dense_hits, sparse_hits, local_hits]) else []

    reranked = rerank_candidates(query, hybrid_candidates, top_k=top_k) if hybrid_candidates else []
    if reranked and reranked[0]["score"] >= SCORE_THRESHOLD:
        return reranked[:top_k]

    fallback = local_hits[:top_k]
    if fallback:
        return fallback

    try:
        from Lab_Assigment.src.task8_pageindex_vectorless import pageindex_search
    except Exception:
        return []

    pageindex_hits = pageindex_search(query, top_k=top_k)
    filtered = []
    for hit in pageindex_hits:
        metadata = dict(hit.get("metadata", {}))
        metadata.setdefault("source", "pageindex")
        filtered.append({
            "content": hit.get("content", ""),
            "score": float(hit.get("score", 0.0)),
            "metadata": metadata,
            "source": hit.get("source", "pageindex"),
        })
    return filtered[:top_k]


def build_source_list(hits: list[dict[str, Any]]) -> list[str]:
    return [source_label(hit) for hit in hits]

