# System Architecture — Multi-Tenant WhatsApp AI Agent

## What This System Is

A SaaS platform where multiple companies (tenants) each get their own AI-powered WhatsApp
customer support bot. One codebase, one deployment — multiple tenants isolated by tenant_id.

---

## Tech Stack (All Free Tier)

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | FastAPI (Python) | LangGraph is Python-native |
| Primary LLM | Groq — llama-3.3-70b-versatile | Free, fast, tool calling support |
| Multimodal LLM | Google Gemini 1.5 Flash | Free, vision capable (bonus B2) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | Local, free, no API cost |
| App Database | MongoDB Atlas M0 | Free forever, explicitly in requirements |
| Vector Store | Chroma DB (embedded) | Runs inside FastAPI process, free |
| Frontend | React + Vite + Tailwind CSS | Fast, free |
| Backend Deploy | Render.com (free web service) | Free HTTPS, Docker support |
| Frontend Deploy | Vercel | Free forever |
| Keep-Alive | UptimeRobot (free) | Pings /health every 14 min, prevents Render sleep |

---

## Component Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                         CUSTOMER (WhatsApp)                          │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ sends message
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    META CLOUD API (WhatsApp)                         │
│                POST webhook to your server                           │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND (Render)                        │
│                                                                      │
│  POST /api/webhooks/whatsapp                                         │
│    ├── Returns 200 OK IMMEDIATELY (< 1 second)                       │
│    └── Fires asyncio background task ──────────────────────┐        │
│                                                            │        │
│  GET /api/webhooks/whatsapp                                │        │
│    └── Meta verification challenge                         │        │
│                                                            │        │
│  GET /api/tenants                                          │        │
│  GET /api/tenants/{id}/sessions                            │        │
│  GET /api/sessions/{id}/messages                           │        │
│  POST /api/broadcast                                       │        │
│                                                            │        │
│  /static/* (PDFs, images served here)                     │        │
└────────────────────────────────────────────────────────────┼────────┘
                                                             │
                           ┌─────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     LANGGRAPH PIPELINE                               │
│                                                                      │
│  [Node 1] ACKNOWLEDGE                                                │
│    → send_read_receipt()    ─────────────────────► Meta API         │
│    → send_typing_indicator() ────────────────────► Meta API         │
│    → save inbound message   ─────────────────────► MongoDB          │
│    → set status: AGENT_RESPONDING                                    │
│           │                                                          │
│           ▼                                                          │
│  [Node 2] CONTEXT RETRIEVER                                          │
│    → fetch tenant config    ─────────────────────► MongoDB          │
│    → fetch last 5 messages  ─────────────────────► MongoDB          │
│    → embed user query       ─────────────────────► sentence-t       │
│    → semantic search        ─────────────────────► Chroma DB        │
│    → bundle context into state                                       │
│           │                                                          │
│           ▼                                                          │
│  [Node 3] LLM REASONING                                              │
│    → build prompt (system_prompt + RAG + history + user_msg)        │
│    → call Groq Llama 3.3 70B with 3 tools:                          │
│         • get_media(keyword)                                         │
│         • search_knowledge(query)                                    │
│         • escalate_to_human(reason)                                  │
│    → (if inbound image) call Gemini Vision first                     │
│    → parse: {reply_text, media_type, media_url, new_status}         │
│           │                                                          │
│           ▼                                                          │
│  [Node 4] DISPATCHER                                                 │
│    → send_text_message()    ─────────────────────► Meta API         │
│    → send_image_message()   ─────────────────────► Meta API         │
│    → send_document_message() ────────────────────► Meta API         │
│    → save outbound message  ─────────────────────► MongoDB          │
│    → update session status  ─────────────────────► MongoDB          │
│    [typing indicator auto-stops when bot sends reply]               │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                   REACT DASHBOARD (Vercel)                           │
│                                                                      │
│  TenantSwitcher → ChatMonitor → ChatThread → BroadcastDrawer        │
│                                                                      │
│  Polls /api/tenants/{id}/sessions every 5 seconds for live updates  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Tenant Isolation Strategy

```
One Meta App → One Webhook URL → One FastAPI Server
                                        │
                    Incoming payload contains phone_number_id
                                        │
                    MongoDB tenants lookup: phone_number_id → tenant_id
                                        │
                    ALL subsequent operations scoped to tenant_id:
                    - MongoDB queries: {tenant_id: "tenant_a"}
                    - Chroma queries: metadata filter {tenant_id: "tenant_a"}
                    - Media library: tenant.media_library dict
                    - System prompt: tenant.system_prompt
```

**For demo (single Meta sandbox number):**
- Map customer phone numbers to tenants in seed data
- customer +91XXXXX1 → Tenant A (Luxury Furniture)
- customer +91XXXXX2 → Tenant B (Automotive Care)
- Dashboard shows separate views per tenant

---

## Full Request Lifecycle (Timeline)

```
T+0ms    Customer sends WhatsApp message
T+100ms  Meta fires POST webhook to FastAPI
T+150ms  FastAPI returns 200 OK to Meta  ← CRITICAL (must be < 3000ms)
T+160ms  asyncio background task starts LangGraph
T+200ms  Node 1: read receipt sent to Meta
T+250ms  Node 1: typing indicator ON sent to Meta
T+300ms  Node 1: message saved to MongoDB
T+350ms  Node 2: tenant config + last 5 messages fetched from MongoDB
T+400ms  Node 2: user query embedded by sentence-transformers
T+500ms  Node 2: Chroma semantic search returns 3 relevant chunks
T+600ms  Node 3: Groq Llama 3.3 70B called with full context
T+2000ms Node 3: LLM returns {reply, maybe tool call}
T+2100ms Node 4: WhatsApp message sent (typing indicator stops)
T+2200ms Node 4: outbound message saved to MongoDB
T+2200ms Customer sees reply on WhatsApp
T+2300ms Dashboard reflects updated conversation
```

---

## Folder Structure (Final)

```
Multi_Tenant_Whatsapp_Agent/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry, CORS, static files, router mount
│   │   ├── config.py                # All env vars via pydantic-settings
│   │   ├── db/
│   │   │   ├── mongodb.py           # Motor async client, connection pool
│   │   │   ├── models.py            # Pydantic models for all 3 collections
│   │   │   └── seed.py              # Seed Tenant A + B with media_library
│   │   ├── rag/
│   │   │   ├── chroma_client.py     # Chroma init, collection management
│   │   │   ├── embedder.py          # sentence-transformers wrapper
│   │   │   └── seed_knowledge.py    # Embed + index Tenant A + B docs
│   │   ├── api/
│   │   │   ├── webhooks.py          # POST + GET /api/webhooks/whatsapp
│   │   │   └── dashboard.py         # All dashboard REST endpoints
│   │   ├── whatsapp/
│   │   │   └── client.py            # All 5 Meta API helper methods
│   │   └── agent/
│   │       ├── state.py             # AgentState TypedDict
│   │       ├── nodes.py             # 4 node functions
│   │       ├── tools.py             # get_media, search_knowledge, escalate
│   │       └── graph.py             # Compiled StateGraph
│   ├── static/
│   │   ├── furniture_catalog.pdf    # Tenant A catalog
│   │   ├── sofa.jpg                 # Tenant A sofa image
│   │   ├── showroom.png             # Tenant A showroom
│   │   ├── invoice_template.pdf     # Tenant B invoice
│   │   └── repair_diagram.jpg       # Tenant B diagram
│   ├── chroma_store/                # Chroma persistence (gitignored)
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── TenantSwitcher.jsx
│   │   │   ├── ChatMonitor.jsx
│   │   │   ├── ChatThread.jsx
│   │   │   └── BroadcastDrawer.jsx
│   │   └── api/
│   │       └── client.js            # fetch wrapper for backend
│   ├── package.json
│   └── vite.config.js
├── docs/
│   ├── 01_ARCHITECTURE.md           # This file
│   ├── 02_DATABASE_DESIGN.md
│   ├── 03_RAG_DESIGN.md
│   ├── 04_LANGGRAPH_DESIGN.md
│   ├── 05_WHATSAPP_INTEGRATION.md
│   ├── 06_DEPLOYMENT.md
│   ├── 07_TODO_CHECKLIST.md
│   └── 08_CONFIRM_CHECKS.md
├── docker-compose.yml               # Local dev
└── README.md
```
