# Database Design — MongoDB Atlas M0 + Chroma (In-Memory)

## Why Two Stores

| Store | Purpose | Cost |
|-------|---------|------|
| MongoDB Atlas M0 | All structured app data (tenants, sessions, messages, knowledge raw text) | Free forever |
| Chroma DB (in-memory) | Vector index for RAG semantic search — rebuilt from MongoDB on startup | Free (no disk needed) |

## Chroma Persistence Strategy (Critical Decision)

Render free tier has NO persistent disk. Chroma in-memory solves this cleanly:

```
On FastAPI startup:
  1. Connect to MongoDB
  2. Fetch all knowledge_docs for all tenants
  3. Embed each doc with sentence-transformers (local, free)
  4. Load into Chroma in-memory collection
  5. Ready to serve

On Render restart (happens ~daily or on deploy):
  → Same process repeats, ~10-20 seconds to rebuild index
  → All source docs are safe in MongoDB (persistent)
  → UptimeRobot keeps Render awake so restarts are rare
```

This means MongoDB is the source of truth for knowledge docs. Chroma is just a search index.

---

## MongoDB Collections (3 Total)

### Collection 1: `tenants`

```json
{
  "_id": "ObjectId()",
  "tenant_id": "tenant_a",
  "name": "Luxury Furniture Store",
  "system_prompt": "You are a warm, professional assistant for a luxury furniture brand. Help customers discover our premium collection, answer questions about products, delivery, and showrooms. When customers ask for catalogs or images, use your tools to fetch them.",
  "whatsapp_phone_number_id": "123456789012345",
  "whatsapp_access_token": "EAAxxxxxx",
  "media_library": {
    "catalog": "https://yourapp.onrender.com/static/furniture_catalog.pdf",
    "sofa": "https://yourapp.onrender.com/static/sofa.jpg",
    "showroom": "https://yourapp.onrender.com/static/showroom.png",
    "price list": "https://yourapp.onrender.com/static/price_list.pdf",
    "brochure": "https://yourapp.onrender.com/static/furniture_catalog.pdf"
  },
  "is_active": true,
  "created_at": "ISODate"
}
```

```json
{
  "_id": "ObjectId()",
  "tenant_id": "tenant_b",
  "name": "AutoCare Services",
  "system_prompt": "You are a helpful assistant for an automotive care center. Help customers schedule service appointments, answer questions about car maintenance, and provide invoices or repair diagrams when needed.",
  "whatsapp_phone_number_id": "123456789012345",
  "whatsapp_access_token": "EAAxxxxxx",
  "media_library": {
    "invoice": "https://yourapp.onrender.com/static/invoice_template.pdf",
    "repair diagram": "https://yourapp.onrender.com/static/repair_diagram.jpg",
    "service menu": "https://yourapp.onrender.com/static/invoice_template.pdf",
    "price": "https://yourapp.onrender.com/static/invoice_template.pdf"
  },
  "is_active": true,
  "created_at": "ISODate"
}
```

**Indexes:**
```
tenant_id: unique index
whatsapp_phone_number_id: index
```

---

### Collection 2: `chat_sessions`

```json
{
  "_id": "ObjectId()",
  "session_id": "sess_uuid4",
  "tenant_id": "tenant_a",
  "customer_phone": "+919876543210",
  "status": "AGENT_RESPONDING",
  "context_vars": {},
  "message_count": 7,
  "last_message_at": "ISODate",
  "created_at": "ISODate"
}
```

**Status values (from PDF — all 4 required):**
- `WAITING_FOR_BOT` — customer messaged, LangGraph not yet started
- `AGENT_RESPONDING` — LangGraph is actively processing (typing indicator is ON)
- `RESOLVED` — bot replied successfully, conversation complete
- `NEEDS_HUMAN` — frustration detected, bot halted (bonus B3)

**Indexes:**
```
{tenant_id: 1, customer_phone: 1}: unique compound index
tenant_id: index (for dashboard queries)
status: index (for filtering active sessions)
last_message_at: -1 index (for sorting)
```

**Session Lookup Logic:**
```python
# When webhook arrives:
session = await db.chat_sessions.find_one({
    "tenant_id": tenant_id,
    "customer_phone": customer_phone
})

if not session:
    # New customer — create session
    session = create_new_session(tenant_id, customer_phone)
    status = "WAITING_FOR_BOT"
elif session["status"] == "NEEDS_HUMAN":
    # Bot is halted — do NOT process, just log inbound message
    # Dashboard will show this in red
    return
else:
    # Existing session — continue conversation
    pass
```

---

### Collection 3: `message_audit_log`

```json
{
  "_id": "ObjectId()",
  "message_id": "msg_uuid4",
  "whatsapp_message_id": "wamid.ABGGFlA5FpafAgo6tHcNmNjKADJEQ3bZE3",
  "session_id": "sess_uuid4",
  "tenant_id": "tenant_a",
  "direction": "INBOUND",
  "sender": "+919876543210",
  "text_content": "Can you send me your furniture catalog?",
  "media_url": null,
  "media_type": null,
  "media_mime_type": null,
  "agent_state": "TYPING",
  "is_read": true,
  "timestamp": "ISODate"
}
```

```json
{
  "_id": "ObjectId()",
  "message_id": "msg_uuid4_reply",
  "whatsapp_message_id": "wamid.reply_xxx",
  "session_id": "sess_uuid4",
  "tenant_id": "tenant_a",
  "direction": "OUTBOUND",
  "sender": "BOT",
  "text_content": "Of course! Here is our latest furniture catalog. Feel free to browse and let me know if you need anything.",
  "media_url": "https://yourapp.onrender.com/static/furniture_catalog.pdf",
  "media_type": "DOCUMENT",
  "media_mime_type": "application/pdf",
  "agent_state": "SENT",
  "is_read": false,
  "timestamp": "ISODate"
}
```

**Indexes:**
```
{session_id: 1, timestamp: 1}: compound index (for fetching last 5 messages)
tenant_id: index (for audit queries)
direction: index
timestamp: -1 index
```

---

### Collection 4: `knowledge_docs` (source of truth for RAG)

```json
{
  "_id": "ObjectId()",
  "doc_id": "doc_uuid4",
  "tenant_id": "tenant_a",
  "doc_type": "product",
  "title": "Milano Sofa",
  "content": "The Milano Sofa is crafted from premium Italian leather, available in 8 colors. Dimensions: 220cm x 90cm x 85cm. Price: ₹1,85,000. Delivery: 4-6 weeks. Features adjustable headrests and solid walnut frame.",
  "source": "product_catalog",
  "created_at": "ISODate"
}
```

**Tenant A docs (pre-seeded):**
- Product descriptions (Milano Sofa, Valencia Dining Set, Monaco Bed Frame, etc.)
- FAQs (delivery, warranty, customization, showroom locations)
- Pricing guide

**Tenant B docs (pre-seeded):**
- Service packages (oil change, brake service, AC service, etc.)
- Common car issues + solutions
- Appointment policy

**Indexes:**
```
tenant_id: index (for rebuilding Chroma index per tenant)
doc_type: index
```

---

## Chroma DB Design (In-Memory, Rebuilt on Startup)

```python
# Single collection, metadata-filtered per tenant
collection_name = "knowledge_base"

# Document structure in Chroma:
{
  "id": "doc_uuid4",
  "document": "The Milano Sofa is crafted from premium Italian leather...",
  "metadata": {
    "tenant_id": "tenant_a",
    "doc_type": "product",
    "title": "Milano Sofa",
    "doc_id": "doc_uuid4"
  }
}

# Query ALWAYS filtered by tenant_id:
results = collection.query(
    query_embeddings=[user_embedding],
    where={"tenant_id": "tenant_a"},   # CRITICAL: always filter by tenant
    n_results=3
)

# Only use results with sufficient similarity (cosine distance < 0.4 = similarity > 0.7):
filtered = [r for r, d in zip(results, distances) if d < 0.4]
```

---

## Environment Variables Required

```bash
# MongoDB
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/whatsapp_agent

# Meta WhatsApp
META_PHONE_NUMBER_ID=123456789012345
META_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxx
META_VERIFY_TOKEN=your_custom_verify_token_here
META_APP_SECRET=your_app_secret_for_signature_validation

# LLM (decided after agent research)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxx

# App
APP_BASE_URL=https://yourapp.onrender.com
```
