"""
Task 5 — Semantic Search Module.

Viết module tìm kiếm ngữ nghĩa (dense retrieval) trên vector store.

Yêu cầu:
    - Input: query string + top_k
    - Output: danh sách chunks có score, sorted descending
    - Phải tương thích với embedding model và vector store ở Task 4
"""


_semantic_model = None
_data_store = None
_embeddings = None

def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,      # Nội dung chunk
            'score': float,      # Cosine similarity score
            'metadata': dict     # source, doc_type, chunk_index
        }
        Sorted by score descending.
    """
    import json
    import numpy as np
    from pathlib import Path
    from sentence_transformers import SentenceTransformer
    import sys
    
    global _semantic_model, _data_store, _embeddings

    if _semantic_model is None:
        DATA_DIR = Path(__file__).parent.parent / "data"
        try:
            with open(DATA_DIR / "vector_store.json", "r", encoding="utf-8") as f:
                _data_store = json.load(f)
            _embeddings = np.load(DATA_DIR / "vector_store_embeddings.npy")
        except FileNotFoundError:
            return []

        # Model parameters must match Task 4
        _semantic_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        
    query_embedding = _semantic_model.encode([query])[0]

    # Calculate cosine similarity
    # We can use dot product if embeddings are normalized, otherwise cosine sim formula:
    query_norm = np.linalg.norm(query_embedding)
    embeddings_norm = np.linalg.norm(_embeddings, axis=1)
    
    similarities = np.dot(_embeddings, query_embedding) / (embeddings_norm * query_norm)
    
    # Get top_k indices
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    results = []
    for idx in top_indices:
        results.append({
            "content": _data_store[idx]["content"],
            "score": float(similarities[idx]),
            "metadata": _data_store[idx]["metadata"]
        })
        
    return results


if __name__ == "__main__":
    # Test
    results = semantic_search("hình phạt cho tội tàng trữ ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
