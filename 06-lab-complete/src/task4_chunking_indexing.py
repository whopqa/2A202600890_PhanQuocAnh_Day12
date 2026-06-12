"""
Task 4 — Chunking & Indexing vào Vector Store.

Hướng dẫn:
    1. Đọc toàn bộ markdown files từ data/standardized/
    2. Chọn 1 chunking strategy (giải thích lý do)
    3. Chọn 1 embedding model (giải thích lý do)
    4. Index vào vector store (Weaviate khuyến cáo)

Chunking options (langchain-text-splitters):
    - RecursiveCharacterTextSplitter: an toàn, phổ biến
    - MarkdownHeaderTextSplitter: tốt cho file có heading
    - SemanticChunker: dùng embedding để tách (nâng cao)

Embedding model options:
    - sentence-transformers/all-MiniLM-L6-v2 (384 dim, nhẹ)
    - BAAI/bge-m3 (1024 dim, multilingual, tốt cho tiếng Việt)
    - OpenAI text-embedding-3-small (1536 dim, API)

Vector store options:
    - Weaviate (khuyến cáo: hỗ trợ hybrid search built-in)
    - ChromaDB (đơn giản, local)
    - FAISS (chỉ dense search)

Cài đặt:
    pip install langchain-text-splitters sentence-transformers weaviate-client
"""

from pathlib import Path

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn của bạn trong comment
# =============================================================================

# Tại sao chọn CHUNK_SIZE = 500?
# - Dữ liệu luật pháp và tin tức thường có cấu trúc câu dài vừa phải. 500 ký tự
#   đảm bảo giữ được khoảng 1-2 đoạn văn trọn vẹn ý nghĩa, giúp Embedding model
#   không bị nhiễu bởi quá nhiều thông tin không liên quan.
CHUNK_SIZE = 500

# Tại sao chọn CHUNK_OVERLAP = 50?
# - Overlap 50 ký tự (khoảng 10-15 từ) để đảm bảo các từ khóa kết nối giữa hai
#   đoạn chunk không bị cắt đứt, giúp duy trì ngữ cảnh liền mạch cho LLM.
CHUNK_OVERLAP = 50

# Tại sao chọn CHUNKING_METHOD = "recursive"?
# - RecursiveCharacterTextSplitter tách văn bản dần dần từ paragraph -> sentence -> word,
#   đây là cách an toàn và tự nhiên nhất để không làm vỡ cấu trúc câu ngữ pháp, 
#   đặc biệt hữu ích khi xử lý tài liệu markdown.
CHUNKING_METHOD = "recursive"

# Tại sao chọn model này?
# - "all-MiniLM-L6-v2" là model rất nhẹ (chỉ tốn khoảng 80MB dung lượng), chạy cực
#   kỳ nhanh trên CPU nhưng vẫn cho ra chất lượng embedding 384-chiều rất tốt cho
#   tác vụ semantic search cơ bản.
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Tại sao chọn vector store local_numpy?
# - Không cần setup server cồng kềnh như Weaviate hay FAISS cho một bài lab nhỏ.
#   Numpy array cho tốc độ đủ nhanh (O(N) brute-force) với dữ liệu quy mô nhỏ (vài nghìn chunks),
#   việc lưu trữ và load lại qua file .npy rất dễ dàng.
VECTOR_STORE = "local_numpy"


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    documents = []
    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        doc_type = "legal" if "legal" in str(md_file) else "news"
        documents.append({
            "content": content,
            "metadata": {"source": md_file.name, "type": doc_type}
        })
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo strategy đã chọn.

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = []
    for doc in documents:
        splits = splitter.split_text(doc["content"])
        for i, chunk_text in enumerate(splits):
            chunks.append({
                "content": chunk_text,
                "metadata": {**doc["metadata"], "chunk_index": i}
            })
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn.

    Returns:
        Mỗi chunk dict được thêm key 'embedding': list[float]
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL)
    texts = [c["content"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False)
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist()
    return chunks


def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks vào vector store đã chọn.
    """
    import json
    import numpy as np

    data_store = []
    vectors = []
    for c in chunks:
        data_store.append({
            "content": c["content"],
            "metadata": c["metadata"]
        })
        vectors.append(c["embedding"])

    # Lưu xuống thư mục data/
    DATA_DIR = Path(__file__).parent.parent / "data"
    DATA_DIR.mkdir(exist_ok=True)
    
    with open(DATA_DIR / "vector_store.json", "w", encoding="utf-8") as f:
        json.dump(data_store, f, ensure_ascii=False)
    
    np.save(DATA_DIR / "vector_store_embeddings.npy", np.array(vectors, dtype=np.float32))


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n✓ Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"✓ Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"✓ Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("✓ Indexed to vector store")


if __name__ == "__main__":
    run_pipeline()
