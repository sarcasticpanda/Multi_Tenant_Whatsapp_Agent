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

    ids, documents, metadatas = [], [], []

    # 1. Knowledge docs (FAQs, policies, text) -> type "knowledge"
    docs = await db.knowledge_docs.find({}).to_list(None)
    for doc in docs:
        ids.append(doc["doc_id"])
        documents.append(doc["content"])
        metadatas.append({
            "tenant_id": doc["tenant_id"],
            "type": "knowledge",
            "title": doc["title"],
        })

    # 2. Catalog items (visual products) -> type "catalog", carries image_url + price
    items = await db.catalog_items.find({"is_active": True}).to_list(None)
    for it in items:
        ids.append(it["item_id"])
        # Search text = name + description + key attributes (so "green leather sofa" matches)
        attr_text = " ".join(f"{k}: {v}" for k, v in (it.get("attributes") or {}).items())
        documents.append(f"{it['name']}. {it.get('ai_description','')} {attr_text} Price: {it.get('price','')}")
        metadatas.append({
            "tenant_id": it["tenant_id"],
            "type": "catalog",
            "title": it["name"],
            "image_url": it["image_url"],
            "price": it.get("price", ""),
        })

    if not ids:
        print("No documents found in MongoDB. Skipping Chroma index build.")
        return _collection

    _collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Chroma index built: {len(docs)} knowledge + {len(items)} catalog = {_collection.count()} vectors")
    return _collection


def get_chroma_collection():
    if _collection is None:
        raise RuntimeError("Chroma not initialised. Call build_chroma_index() at startup.")
    return _collection


def search_knowledge_base(query: str, tenant_id: str, n_results: int = 3) -> list[str]:
    """
    Semantic search over KNOWLEDGE docs (FAQs, policies, pricing text), tenant-scoped.
    Returns text chunks for the LLM to answer factual questions.
    """
    collection = get_chroma_collection()
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        where={"$and": [{"tenant_id": tenant_id}, {"type": "knowledge"}]},
        n_results=min(n_results, collection.count()),
        include=["documents", "distances"],
    )

    chunks = []
    if results["documents"] and results["documents"][0]:
        for doc, distance in zip(results["documents"][0], results["distances"][0]):
            if distance < 0.9:  # cosine distance threshold
                chunks.append(doc)
    return chunks


def search_catalog(query: str, tenant_id: str) -> dict | None:
    """
    Semantic search over visual CATALOG items, tenant-scoped.
    Returns the best-matching product with its image_url + price + details,
    or None if nothing is relevant. This is how "show me a green leather sofa"
    fetches the right product image AND its data together.
    """
    collection = get_chroma_collection()
    if collection.count() == 0:
        return None

    results = collection.query(
        query_texts=[query],
        where={"$and": [{"tenant_id": tenant_id}, {"type": "catalog"}]},
        n_results=1,
        include=["documents", "distances", "metadatas"],
    )

    if not results["metadatas"] or not results["metadatas"][0]:
        return None

    meta = results["metadatas"][0][0]
    distance = results["distances"][0][0]
    document = results["documents"][0][0]
    if distance >= 1.0:  # too unrelated — don't surface a wrong product
        return None

    return {
        "name": meta.get("title", ""),
        "image_url": meta.get("image_url", ""),
        "price": meta.get("price", ""),
        "details": document,  # full searchable text (name + desc + attrs + price)
    }
