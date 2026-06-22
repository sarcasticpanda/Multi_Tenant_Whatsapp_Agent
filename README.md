# Multi-Tenant Agentic WhatsApp Orchestrator

An end-to-end, cloud-native **Multi-Tenant WhatsApp AI Support & Sales Agent SaaS**. Multiple
companies (tenants) run their own AI-powered WhatsApp bot from a single deployment. Each tenant
has its own brand personality, knowledge base, and media library. Built with **LangGraph**,
**FastAPI**, **MongoDB**, **ChromaDB (RAG)**, and the **Meta WhatsApp Cloud API**.

---

## Demo Tenants

| Tenant | Persona | Sells | Media |
|--------|---------|-------|-------|
| Tenant A | "Aria" — luxury design concierge | Premium furniture | Catalog PDF, sofa & showroom images, price list |
| Tenant B | "Max" — service advisor | Car servicing | Invoice PDF, repair diagram |

---

## Architecture

```
Customer (WhatsApp)
      │
Meta Cloud API ──POST webhook──►  FastAPI  ──returns 200 OK in <1s──►  Meta
                                     │
                                     └─► asyncio BackgroundTask
                                              │
                                  ┌───────────▼───────────┐
                                  │   LangGraph Pipeline   │
                                  ├────────────────────────┤
                                  │ 1. Acknowledge         │ → read receipt + typing indicator + save inbound
                                  │ 2. Context Retriever   │ → tenant cfg + last 5 msgs + RAG (Chroma) + vision
                                  │ 3. LLM Reasoning       │ → Gemini 2.0 Flash + tools (get_media / search / escalate)
                                  │ 4. Dispatcher          │ → send text/image/doc + save + update status
                                  └────────────────────────┘
                                     │              │
                                  MongoDB        ChromaDB (in-memory RAG, rebuilt from MongoDB on boot)
```

### LangGraph State Schema
`AgentState` (TypedDict) flows through all 4 nodes:
- **Inbound**: tenant_id, customer_phone, session_id, whatsapp_message_id, inbound_text, inbound_media_id, inbound_image_description
- **Retrieved** (Node 2): tenant_config, chat_history (last 5), rag_chunks
- **LLM output** (Node 3): llm_reply, media_to_send, media_type, media_filename
- **Session**: session_status (WAITING_FOR_BOT → AGENT_RESPONDING → RESOLVED | NEEDS_HUMAN)

### Nodes & Edges
```
START → acknowledge → retrieve_context → llm_reason → dispatch → END
```
- **acknowledge** — fires WhatsApp read receipt + typing indicator instantly, saves inbound message, sets AGENT_RESPONDING.
- **retrieve_context** — loads tenant config + last 5 messages from MongoDB, runs RAG semantic search (Chroma, tenant-filtered), and (bonus) describes any inbound image via Gemini Vision.
- **llm_reason** — calls Gemini 2.0 Flash with 3 tools: `get_media` (media library lookup), `search_knowledge` (extra RAG), `escalate_to_human` (frustration handover).
- **dispatch** — sends the reply (text + optional image/document) via WhatsApp, saves the outbound message, sets RESOLVED (or NEEDS_HUMAN). Typing indicator auto-extinguishes when the bot replies.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI (Python 3.11) |
| Agent orchestration | LangGraph |
| Primary LLM | Google Gemini 2.0 Flash (free tier, tool calling + vision) |
| Fallback LLM | Groq Llama 3.3 70B (used only if Gemini errors/rate-limits) |
| Embeddings (RAG) | ChromaDB built-in ONNX `all-MiniLM-L6-v2` (no torch — light) |
| App database | MongoDB Atlas (M0 free) |
| Vector store | ChromaDB (in-memory, rebuilt from MongoDB at startup) |
| Messaging | Meta WhatsApp Business Cloud API (Graph API v20.0) |
| Frontend | React + Vite + Tailwind CSS |
| Deployment | Render (backend) + Vercel (frontend) |

---

## Database Schema (MongoDB)

- **tenants** — `tenant_id, name, system_prompt, whatsapp_phone_number_id, media_library{keyword→URL}`
- **chat_sessions** — `session_id, tenant_id, customer_phone, status, message_count, last_message_at`
- **message_audit_log** — `direction, sender, text_content, media_url, media_type, agent_state, timestamp`
- **knowledge_docs** — `tenant_id, doc_type, title, content` (source of truth for RAG; embedded into Chroma on boot)
- **processed_webhooks** — `whatsapp_message_id` (unique; webhook idempotency / dedup)

---

## Environment Variables (.env)

```bash
# MongoDB
MONGO_URI=mongodb+srv://USER:PASS@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=whatsapp_agent

# Meta WhatsApp Cloud API
META_PHONE_NUMBER_ID=your_phone_number_id
META_ACCESS_TOKEN=your_access_token          # use a permanent System User token in production
META_VERIFY_TOKEN=any_string_you_choose
META_APP_SECRET=your_app_secret              # enables X-Hub-Signature-256 validation

# LLM
GEMINI_API_KEY=your_gemini_key               # aistudio.google.com
GEMINI_MODEL=gemini-2.0-flash
GROQ_API_KEY=your_groq_key                   # console.groq.com (fallback)

# App
APP_BASE_URL=https://your-backend.onrender.com
```

---

## Run Locally

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env           # then fill in your values
uvicorn app.main:app --reload --port 8000
```
On startup the app connects to MongoDB, seeds the 2 demo tenants + knowledge docs (if empty),
and builds the Chroma RAG index. Visit http://localhost:8000/docs for the API.

### Expose webhook for local testing (ngrok)
```bash
ngrok http 8000
# set APP_BASE_URL in .env to the https ngrok URL, restart backend
# point the Meta webhook to  https://<ngrok>/api/webhooks/whatsapp
```

### Frontend
```bash
cd frontend
npm install
echo VITE_API_BASE_URL=http://localhost:8000 > .env
npm run dev      # http://localhost:5173
```

---

## Deployment

### Backend → Render
1. Push to GitHub.
2. Render → New → Web Service → connect repo → Root: `backend`, Runtime: Docker.
3. Add all env vars (above). Instance: Free.
4. Deploy → note your `https://<app>.onrender.com` URL.
5. (Optional) UptimeRobot pings `/health` every 5 min to prevent free-tier sleep.

### Frontend → Vercel
1. Vercel → New Project → import repo → Root: `frontend`, framework: Vite.
2. Env: `VITE_API_BASE_URL=https://<app>.onrender.com`.
3. Deploy.

### Meta Webhook
- Callback URL: `https://<app>.onrender.com/api/webhooks/whatsapp`
- Verify token: your `META_VERIFY_TOKEN`
- Subscribe to the `messages` field.

---

## Features

### Core (assignment Tasks 1–6)
- Multi-tenant DB schema with full isolation
- WhatsApp read receipts, native typing indicator, text (`*bold*` / `_italics_`), image & document sending
- LangGraph 4-node agent
- Async webhook — returns 200 OK in <1s, runs the agent in the background (Meta never times out)
- Dashboard: tenant switcher, live chat monitor (image thumbnails, PDF badges, typing indicator, NEEDS_HUMAN in red), broadcast drawer
- Containerized + cloud deployed

### Bonus
- **Webhook security** — X-Hub-Signature-256 HMAC validation (enforced when `META_APP_SECRET` set)
- **Inbound media parsing** — customer-sent images described by Gemini Vision and fed into the conversation
- **Fallback handover** — frustration detection → `NEEDS_HUMAN`, auto-replies halt, chat highlighted red on the dashboard

### Reliability engineering
- **Webhook idempotency** — unique index on `whatsapp_message_id`; Meta retries never double-process
- **Atomic session creation** — `find_one_and_update(upsert)` avoids race conditions
- **LLM fallback** — Groq used automatically if Gemini errors or rate-limits
- **Tenant-filtered RAG** — every Chroma query is scoped by `tenant_id` (no cross-tenant leakage)

---

## Project Structure
```
backend/
  app/
    main.py            # FastAPI app + lifespan (connect DB, seed, build RAG)
    config.py          # env settings
    db/                # mongodb.py, models.py, seed.py
    rag/               # chroma_client.py, seed_knowledge.py
    whatsapp/          # client.py (Meta API helpers + signature validation)
    agent/             # state.py, tools.py, nodes.py, graph.py
  static/              # tenant media (PDFs, images)
  Dockerfile
  requirements.txt
frontend/
  src/
    App.jsx
    components/        # TenantSwitcher, ChatMonitor, ChatThread, BroadcastDrawer
    api/client.js
docs/                  # architecture, DB design, RAG, LangGraph, deployment specs
```

---

## Notes & Limitations
- Demo uses one Meta **test number** shared by both tenants (sandbox limit). In production each tenant maps to its own `phone_number_id`.
- Broadcast uses free-form text, which Meta only allows inside the 24-hour customer-service window; production broadcasts require pre-approved message templates.
- ChromaDB runs in-memory and rebuilds from MongoDB on each restart (fine for this scale; a managed vector DB would be used at larger scale).
