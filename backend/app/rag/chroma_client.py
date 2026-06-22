import chromadb
from chromadb.utils import embedding_functions
from app.db.mongodb import get_db

_collection = None

# ChromaDB's built-in default embedding = ONNX all-MiniLM-L6-v2 (~80MB via onnxruntime).
# Same model as sentence-transformers but WITHOUT torch (~2GB) — fits Render free tier.
_embedding_fn = embedding_functions.DefaultEmbeddingFunction()


async def build_chroma_index():
    """
    Fetches all knowledge_docs from MongoDB and loads them into
    an in-memory Chroma collection. Called once at FastAPI startup.
    Uses ONNX MiniLM embeddings (lightweight, no torch).
    """
    global _collection

    client = chromadb.Client()  # in-memory, no disk needed
    _collection = client.get_or_create_collection(
        name="knowledge_base",
        embedding_function=_embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    db = get_db()
    docs = await db.knowledge_docs.find({}).to_list(None)

    if not docs:
        print("No knowledge docs found in MongoDB. Skipping Chroma index build.")
        return _collection

    ids = [doc["doc_id"] for doc in docs]
    documents = [doc["content"] for doc in docs]
    metadatas = [
        {
            "tenant_id": doc["tenant_id"],
            "doc_type": doc["doc_type"],
            "title": doc["title"],
        }
        for doc in docs
    ]

    # Upsert in one batch
    _collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Chroma index built: {len(docs)} docs loaded ({_collection.count()} vectors)")
    return _collection


def get_chroma_collection():
    if _collection is None:
        raise RuntimeError("Chroma not initialised. Call build_chroma_index() at startup.")
    return _collection


def search_knowledge_base(query: str, tenant_id: str, n_results: int = 3) -> list[str]:
    """
    Semantic search filtered strictly by tenant_id.
    Only returns chunks with cosine distance < 0.5 (~similarity > 0.75).
    Returns empty list if nothing relevant — safe fallback.
    """
    collection = get_chroma_collection()

    # Guard: if collection is empty return nothing
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        where={"tenant_id": tenant_id},  # ALWAYS filter — no cross-tenant leakage
        n_results=min(n_results, collection.count()),
        include=["documents", "distances", "metadatas"],
    )

    chunks = []
    if results["documents"] and results["documents"][0]:
        for doc, distance in zip(results["documents"][0], results["distances"][0]):
            # cosine distance: 0 = identical, 2 = opposite.
            # 0.9 keeps good recall for paraphrased questions ("what's the price of X")
            # while still filtering clearly-unrelated chunks.
            if distance < 0.9:
                chunks.append(doc)

    return chunks
