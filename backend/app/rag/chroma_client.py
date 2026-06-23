import asyncio
import chromadb
from chromadb.utils import embedding_functions
from app.db.mongodb import get_db

_client = None
_collection = None
_ready = False                  # True once the index has been built from Mongo at least once
_build_lock = asyncio.Lock()    # serialize builds so a cold-start race can't double-build

# ChromaDB's built-in default embedding = ONNX all-MiniLM-L6-v2 (~80MB via onnxruntime).
# Same model as sentence-transformers but WITHOUT torch (~2GB) — fits Render free tier.
_embedding_fn = embedding_functions.DefaultEmbeddingFunction()


def _get_client():
    """One in-memory Chroma client for the whole process (don't recreate per build)."""
    global _client
    if _client is None:
        _client = chromadb.Client()  # in-memory, no disk needed
    return _client


async def ensure_index_ready():
    """
    Guarantee the in-memory index is built from Mongo before it's queried or upserted.

    Why this exists: the index lives in memory and is lost on every restart. Render's free
    tier sleeps after ~15 min, so the request that *wakes* the service would otherwise query
    an empty index and silently get no RAG results. This builds it on first use (lock-guarded,
    idempotent) so search/upsert can never operate on a missing index. Self-heals if a previous
    build failed (_ready stays False, so the next call retries).
    """
    global _ready
    if _ready and _collection is not None:
        return _collection
    async with _build_lock:
        if _ready and _collection is not None:   # built while we waited for the lock
            return _collection
        await build_chroma_index()
    return _collection


async def build_chroma_index():
    """
    Fetches all knowledge_docs + catalog_items from MongoDB and loads them into the
    in-memory Chroma collection. Runs at startup and whenever the index needs (re)building.
    Uses ONNX MiniLM embeddings (lightweight, no torch).
    """
    global _collection, _ready

    client = _get_client()
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
        _ready = True   # an empty DB is a valid "built" state — don't rebuild on every query
        print("No documents found in MongoDB. Skipping Chroma index build.")
        return _collection

    # Embedding is CPU-bound (ONNX). Run it OFF the event loop so it never freezes
    # the webhook server while a (re)build is in progress.
    await asyncio.to_thread(
        _collection.upsert, ids=ids, documents=documents, metadatas=metadatas
    )
    _ready = True
    print(f"Chroma index built: {len(docs)} knowledge + {len(items)} catalog = {_collection.count()} vectors")
    return _collection


def get_chroma_collection():
    return _collection  # may be None while the background index build is in progress


def catalog_doc_text(item: dict) -> str:
    """The searchable text for a catalog item (must match build_chroma_index)."""
    attr_text = " ".join(f"{k}: {v}" for k, v in (item.get("attributes") or {}).items())
    return f"{item['name']}. {item.get('ai_description','')} {attr_text} Price: {item.get('price','')}"


async def index_upsert(rows: list[dict]) -> None:
    """Incrementally add/update a few vectors — NO full rebuild. rows: [{id, document, metadata}].
    This makes adding knowledge/catalog instant instead of re-embedding the whole DB.

    Ensures the index exists first: an upload right after a cold start used to find
    _collection is None and silently drop the new vectors (chunks landed in Mongo but were
    invisible to the bot until a manual rebuild). Now we build-from-Mongo on demand."""
    if not rows:
        return
    await ensure_index_ready()
    if _collection is None:
        return
    await asyncio.to_thread(
        _collection.upsert,
        ids=[r["id"] for r in rows],
        documents=[r["document"] for r in rows],
        metadatas=[r["metadata"] for r in rows],
    )


async def index_remove(ids: list[str]) -> None:
    """Incrementally delete vectors by id — NO full rebuild."""
    if _collection is None or not ids:
        return
    try:
        await asyncio.to_thread(_collection.delete, ids=list(ids))
    except Exception as e:
        print(f"index_remove failed: {e}")


def search_knowledge_base(query: str, tenant_id: str, n_results: int = 3) -> list[str]:
    """
    Semantic search over KNOWLEDGE docs (FAQs, policies, pricing text), tenant-scoped.
    Returns text chunks for the LLM to answer factual questions.
    Returns [] if the index isn't ready yet (bot still replies from system prompt).
    """
    collection = get_chroma_collection()
    if collection is None or collection.count() == 0:
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
    if collection is None or collection.count() == 0:
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
