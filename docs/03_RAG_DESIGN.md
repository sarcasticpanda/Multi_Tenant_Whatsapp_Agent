# RAG Design — Retrieval Augmented Generation

## Why RAG in This System

The media_library handles simple keyword → URL lookups (get_media tool).
RAG handles the harder problem: user asks "what sofas do you have?" — no exact keyword match,
needs semantic understanding of the tenant's product knowledge base.

RAG makes the bot answer accurately from real tenant data instead of hallucinating.

---

## What Gets Stored in RAG (Per Tenant)

### Tenant A — Luxury Furniture Store
```
product_descriptions/
  - Milano Sofa (leather, dimensions, price, delivery)
  - Valencia Dining Set (8-seater, marble top, price)
  - Monaco Bed Frame (king size, upholstered, custom colors)
  - Riviera Coffee Table (glass top, steel frame)
  
faqs/
  - Delivery timeline and zones
  - Warranty policy (3 years structural, 1 year fabric)
  - Customization options (colors, fabrics, sizes)
  - Showroom locations (Mumbai, Delhi, Bangalore)
  - EMI/financing options
  - Return policy

pricing/
  - General price range guide by category
```

### Tenant B — AutoCare Services
```
services/
  - Oil Change (standard, synthetic, diesel)
  - Brake Service (pads, rotors, fluid)
  - AC Service (regas, compressor check)
  - Tire rotation and alignment
  
faqs/
  - How to book an appointment
  - Service duration estimates
  - Warranty on service work
  - Accepted car brands
  - Payment methods

pricing/
  - Service package pricing (basic, premium, elite)
```

---

## Embedding Model

```
Model: sentence-transformers/all-MiniLM-L6-v2
Source: HuggingFace (downloaded locally, no API key needed)
Dimensions: 384
Speed: ~50ms per sentence on CPU
Cost: FREE — runs inside FastAPI process
```

Why this model:
- Runs on CPU (Render free tier has no GPU)
- Tiny download (~90MB)
- Good semantic quality for product/FAQ retrieval
- Native Chroma integration (no extra code)

---

## Chroma DB Setup (In-Memory + MongoDB Source of Truth)

### Startup Sequence

```python
# app/rag/chroma_client.py

async def build_chroma_index():
    """
    Called once at FastAPI startup.
    Reads all knowledge_docs from MongoDB → embeds → loads to Chroma.
    Takes ~10-20 seconds depending on doc count.
    """
    client = chromadb.Client()  # in-memory, no disk
    collection = client.get_or_create_collection(
        name="knowledge_base",
        embedding_function=SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    )
    
    # Fetch all docs from MongoDB
    docs = await db.knowledge_docs.find({}).to_list(None)
    
    # Batch upsert into Chroma
    collection.upsert(
        ids=[doc["doc_id"] for doc in docs],
        documents=[doc["content"] for doc in docs],
        metadatas=[{
            "tenant_id": doc["tenant_id"],
            "doc_type": doc["doc_type"],
            "title": doc["title"]
        } for doc in docs]
    )
    
    return collection
```

### Query Function

```python
def search_knowledge(
    collection,
    query: str,
    tenant_id: str,
    n_results: int = 3,
    similarity_threshold: float = 0.7
) -> list[str]:
    """
    Semantic search filtered by tenant_id.
    Returns empty list if no results above threshold (safe fallback).
    """
    results = collection.query(
        query_texts=[query],
        where={"tenant_id": tenant_id},   # ALWAYS filter by tenant — no cross-tenant leakage
        n_results=n_results,
        include=["documents", "distances", "metadatas"]
    )
    
    chunks = []
    for doc, distance in zip(results["documents"][0], results["distances"][0]):
        # Chroma uses cosine distance: 0 = identical, 2 = opposite
        # distance < 0.5 means similarity > ~0.75 — good enough
        if distance < 0.5:
            chunks.append(doc)
    
    return chunks  # empty list = no relevant knowledge found = LLM uses system prompt only
```

---

## RAG in the LangGraph Pipeline (Node 2: Context Retriever)

```python
async def context_retriever_node(state: AgentState) -> AgentState:
    tenant_id = state["tenant_id"]
    user_message = state["inbound_text"]
    
    # 1. Fetch tenant config from MongoDB
    tenant = await db.tenants.find_one({"tenant_id": tenant_id})
    
    # 2. Fetch last 5 messages from MongoDB
    last_messages = await db.message_audit_log.find(
        {"session_id": state["session_id"]}
    ).sort("timestamp", -1).limit(5).to_list(5)
    last_messages.reverse()  # chronological order
    
    # 3. RAG: search knowledge base
    rag_chunks = search_knowledge(
        collection=chroma_collection,
        query=user_message,
        tenant_id=tenant_id
    )
    
    # 4. Bundle into state
    state["tenant_config"] = tenant
    state["chat_history"] = last_messages
    state["rag_chunks"] = rag_chunks
    
    return state
```

---

## How RAG Context Gets Injected Into LLM Prompt

```python
def build_system_prompt(tenant: dict, rag_chunks: list[str]) -> str:
    prompt = tenant["system_prompt"]
    
    if rag_chunks:
        prompt += "\n\n--- RELEVANT KNOWLEDGE BASE INFORMATION ---\n"
        for i, chunk in enumerate(rag_chunks, 1):
            prompt += f"\n[{i}] {chunk}\n"
        prompt += "\n--- END OF KNOWLEDGE BASE ---\n"
        prompt += "\nUse the above information to answer accurately. Do not fabricate information not present above."
    else:
        prompt += "\n\nAnswer based on your general knowledge of the brand. If unsure, offer to connect the customer with a human agent."
    
    return prompt
```

---

## Anti-Hallucination Safeguards

| Safeguard | How |
|-----------|-----|
| Tenant isolation | Chroma query always has `where={"tenant_id": tenant_id}` — impossible to leak Tenant B data to Tenant A |
| Similarity threshold | Only chunks with distance < 0.5 are used — garbage retrieval is filtered out |
| Empty fallback | If no chunks pass threshold, LLM uses system prompt only — safe default |
| Explicit instruction | System prompt tells LLM: "Do not fabricate information not in the knowledge base" |
| Last 5 messages | Conversation history prevents context drift and repetitive answers |

---

## Knowledge Doc Seeding Script

```python
# app/rag/seed_knowledge.py

TENANT_A_DOCS = [
    {
        "tenant_id": "tenant_a",
        "doc_type": "product",
        "title": "Milano Sofa",
        "content": "The Milano Sofa is crafted from premium Italian leather, available in 8 colors including Ivory, Cognac, and Midnight Black. Dimensions: 220cm W x 90cm D x 85cm H. Price: ₹1,85,000. Delivery: 4-6 weeks. Features: adjustable headrests, solid walnut frame, 10-year warranty on frame."
    },
    {
        "tenant_id": "tenant_a",
        "doc_type": "product",
        "title": "Valencia Dining Set",
        "content": "Valencia 8-Seater Dining Set with marble top and solid teak base. Table: 240cm x 110cm. Chairs: Italian leather upholstered. Price: ₹3,20,000 for full set. Delivery: 6-8 weeks. Available customizations: marble color (Carrara White, Nero Marquina), chair fabric."
    },
    {
        "tenant_id": "tenant_a",
        "doc_type": "faq",
        "title": "Delivery and Shipping",
        "content": "We deliver across India. Delhi, Mumbai, Bangalore: 4-6 weeks. Other metro cities: 6-8 weeks. Tier-2 cities: 8-10 weeks. Free delivery for orders above ₹1,00,000. Assembly included. Delivery is tracked and you will receive SMS updates."
    },
    {
        "tenant_id": "tenant_a",
        "doc_type": "faq",
        "title": "Warranty Policy",
        "content": "All furniture comes with 3-year structural warranty and 1-year fabric/leather warranty. Warranty covers manufacturing defects. Damages from misuse, water, or pets are not covered. For warranty claims, contact our service team with order number and photos."
    },
    {
        "tenant_id": "tenant_a",
        "doc_type": "faq",
        "title": "Showroom Locations",
        "content": "Showrooms: Mumbai - Bandra West (Mon-Sun 10am-8pm), Delhi - Defence Colony (Mon-Sun 11am-8pm), Bangalore - Indiranagar (Mon-Sun 10am-8pm). Appointments not required but recommended for personalized service."
    },
    {
        "tenant_id": "tenant_a",
        "doc_type": "pricing",
        "title": "Price Range Guide",
        "content": "Sofas: ₹80,000 - ₹4,00,000. Dining sets: ₹1,50,000 - ₹6,00,000. Beds: ₹90,000 - ₹3,50,000. Coffee tables: ₹30,000 - ₹1,50,000. EMI available: 0% EMI for 12 months on HDFC/ICICI cards above ₹1,00,000."
    }
]

TENANT_B_DOCS = [
    {
        "tenant_id": "tenant_b",
        "doc_type": "service",
        "title": "Oil Change Service",
        "content": "Standard mineral oil change: ₹1,200 (includes filter, 5-point inspection). Semi-synthetic: ₹1,800. Full synthetic: ₹2,500. Diesel engines: additional ₹300. Recommended every 5,000 km (mineral) or 10,000 km (synthetic). Duration: 45-60 minutes."
    },
    {
        "tenant_id": "tenant_b",
        "doc_type": "service",
        "title": "Brake Service",
        "content": "Brake pad replacement: ₹2,500 per axle (pads + labour). Brake rotor replacement: ₹4,500 per rotor. Brake fluid change: ₹800. Full brake overhaul (4 wheels): ₹12,000. 6-month warranty on parts. Duration: 2-3 hours."
    },
    {
        "tenant_id": "tenant_b",
        "doc_type": "faq",
        "title": "Appointment Booking",
        "content": "Book appointments via WhatsApp, phone, or walk-in. Service hours: Mon-Sat 8am-7pm, Sunday 9am-3pm. Typical wait time without appointment: 2-4 hours. With appointment: start within 30 minutes. We service all major car brands: Maruti, Hyundai, Tata, Honda, Toyota, Mahindra, KIA, MG."
    },
    {
        "tenant_id": "tenant_b",
        "doc_type": "service",
        "title": "AC Service",
        "content": "AC gas recharge (R134a): ₹1,500. AC compressor check: ₹500. Full AC service (cleaning, recharge, leak check): ₹3,500. Cabin filter replacement: ₹800. Duration: 1-2 hours. 3-month warranty on gas recharge."
    },
    {
        "tenant_id": "tenant_b",
        "doc_type": "pricing",
        "title": "Service Packages",
        "content": "Basic Package (₹2,500): Oil change + tire rotation + 15-point inspection. Silver Package (₹5,500): Basic + brake check + AC check + battery test. Gold Package (₹9,500): Silver + full AC service + coolant flush + spark plugs. All packages include free wash."
    }
]
```

---

## RAG Flow Summary

```
User: "What sofas do you have under 2 lakhs?"
   ↓
Embed query → [0.23, -0.45, 0.12, ...]  (384 dimensions)
   ↓
Chroma query: WHERE tenant_id = "tenant_a", n_results = 3
   ↓
Results:
  [1] "Milano Sofa... Price: ₹1,85,000..." distance=0.18 ✓
  [2] "Price Range Guide: Sofas ₹80,000 - ₹4,00,000..." distance=0.31 ✓
  [3] "Valencia Dining Set... Price ₹3,20,000..." distance=0.51 ✗ (filtered out)
   ↓
Inject chunks [1] and [2] into system prompt
   ↓
Gemini 2.5 Flash responds with accurate, grounded answer
   ↓
"We have the Milano Sofa at ₹1,85,000, which fits your budget! We also have options
 ranging from ₹80,000. Would you like me to send our full catalog?"
   ↓
(LLM calls get_media("catalog") tool → sends PDF)
```
