# Multi-Tenant Agentic WhatsApp Orchestrator

An end-to-end, cloud-native **Multi-Tenant WhatsApp AI Support & Sales Agent SaaS**. Multiple
companies (tenants) run their own AI-powered WhatsApp bot from a single deployment — each with its
own brand persona, knowledge base, media library and catalog, fully isolated. Built with
**LangGraph**, **FastAPI**, **MongoDB**, **ChromaDB (RAG)** and the **Meta WhatsApp Cloud API**.

---

## 🔗 Live Demo

| | URL |
|---|---|
| **Admin dashboard** | https://multi-tenant-whatsapp-agent.vercel.app |
| **Backend / webhook** | https://whatsapp-agent-backend-production-3f9e.up.railway.app |
| **Dashboard password** | `kredai_admin` _(also shown on the login screen for reviewers)_ |

> The bot runs on a Meta **sandbox test number** shared by both demo tenants. The dashboard is
> password-gated; conversation data shown is demo/test data only.

---

## Demo Tenants

| Tenant | Persona | Business | Sends |
|--------|---------|----------|-------|
| **Luxury Furniture Store** | "Aria" — design concierge | Premium furniture | Catalog PDF, product images, price list |
| **AutoCare Services** | "Max" — service advisor | Car servicing | Invoice/menu PDF, repair diagram |

> New tenants can be created and populated entirely from the admin dashboard — name, persona, catalog, media and knowledge — with the RAG index updating live.

---

## 📸 Screenshots

| Live chat monitor (catalog PDF + RAG answers) | Catalog management |
|---|---|
| ![Conversation](frontend/screenshots/conversation.png) | ![Catalog](frontend/screenshots/admin-catalog.png) |
| **Tenant directory** | **Login** |
| ![Tenants](frontend/screenshots/tenants.png) | ![Login](frontend/screenshots/login.png) |

---

## Architecture

```
Customer (WhatsApp)
      │
Meta Cloud API ──POST webhook──►  FastAPI  ──returns 200 OK in <1s──►  Meta
                                     │
                                     ├─► resolve tenant (number / keyword triage / assignment)
                                     │
                                     └─► asyncio BackgroundTask
                                              │
                                  ┌───────────▼───────────┐
                                  │   LangGraph Pipeline   │
                                  ├────────────────────────┤
                                  │ 1. Acknowledge         │ → read receipt + typing indicator + save inbound
                                  │ 2. Context Retriever   │ → tenant cfg + last 5 msgs + RAG (Chroma) + vision
                                  │ 3. LLM Reasoning       │ → Groq Llama 3.3 70B + tools
                                  │ 4. Dispatcher          │ → send text/image/doc + save + update status
                                  └────────────────────────┘
                                     │              │
                                  MongoDB        ChromaDB (in-memory RAG, rebuilt from MongoDB on boot)
```

### LangGraph state & nodes
`AgentState` (TypedDict) flows through 4 nodes: `START → acknowledge → retrieve_context → llm_reason → dispatch → END`.
- **acknowledge** — fires WhatsApp read receipt + typing indicator instantly, saves the inbound message, sets `AGENT_RESPONDING`.
- **retrieve_context** — loads tenant config + last 5 messages, runs tenant-scoped RAG (Chroma), and (bonus) describes any inbound image via Gemini Vision.
- **llm_reason** — Groq Llama 3.3 70B with 4 tools: `get_media`, `search_catalog`, `search_knowledge`, `escalate_to_human`.
- **dispatch** — sends the reply (text + optional image/document), saves it, and updates session status. Typing indicator auto-extinguishes on send.

---

## Multi-tenant routing

One bot number can serve many tenants; a customer is always bound to exactly one tenant (isolated history + RAG). Resolution order:

1. **Explicit assignment** (`customer_routing`) — manual override.
2. **Existing session** — sticky to the tenant they're already in.
3. **Dedicated number** — if a tenant owns the `phone_number_id`, route by number (the production model, scales infinitely).
4. **Keyword triage** (shared number, new customer) — auto-route when the message contains a word unique to one tenant ("sofa" → Furniture, "oil change" → AutoCare). Words shared by tenants ("price") or greetings are *not* confident, so the bot **asks** which business.
5. **Switch anytime** — the customer can text `#autocare` or `switch to AutoCare` to move tenants.

---

## Conversation status lifecycle

| Status | Meaning | Set by |
|--------|---------|--------|
| `WAITING_FOR_BOT` ("Bot active") | Bot on duty; will auto-reply to the next message | new session · after every bot reply · **Resume/Reopen** |
| `AGENT_RESPONDING` ("Replying…") | Bot is generating right now (typing shown) | start of an agent turn (transient) |
| `NEEDS_HUMAN` ("Needs human") | Escalated — auto-replies **paused** | LLM `escalate_to_human` (frustration) · **Take over** |
| `RESOLVED` | Closed by a human | **Resolve** button only |

Dashboard filters: **Active** = open (`WAITING_FOR_BOT` + `AGENT_RESPONDING`), **Escalated** = `NEEDS_HUMAN`, **Resolved** = `RESOLVED`.
When escalated, a human can **reply to the customer directly from the dashboard**.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI (Python) |
| Agent orchestration | LangGraph |
| Primary LLM | **Groq Llama 3.3 70B** (tool calling) |
| Vision LLM | Google Gemini 2.0 Flash (inbound images + catalog auto-describe) |
| Embeddings (RAG) | ChromaDB built-in ONNX `all-MiniLM-L6-v2` |
| Database | MongoDB Atlas (M0 free) |
| File storage | MongoDB GridFS |
| Vector store | ChromaDB (in-memory, rebuilt from MongoDB at startup) |
| Messaging | Meta WhatsApp Business Cloud API (Graph v20.0) |
| Frontend | React + Vite + Tailwind CSS |
| Deployment | **Railway** (backend, Docker) + **Vercel** (frontend) |

## Beyond the assignment

- **Keyword tenant-triage** — auto-route a new customer to the right brand from their words; ask when unsure.
- **Multimodal catalog** — products link an image to structured data, searchable by description.
- **PDF catalog ingestion** — upload one catalog PDF; every product image is extracted, stored in GridFS, and made searchable.
- **Admin panel** — create/delete tenants, manage media/catalog/knowledge, edit persona — all rebuild the RAG index live.
- **Human handover** — escalate, take over, and reply to customers from the dashboard; delete a conversation to re-test.
- **Login gate** — password → signed token protects admin routes.

---

## Database Schema (MongoDB)

- **tenants** — `tenant_id, name, system_prompt, whatsapp_phone_number_id, switch_code, media_library{keyword→URL}`
- **chat_sessions** — `session_id, tenant_id, customer_phone, status, message_count, last_message_at`
- **message_audit_log** — `direction, sender, text_content, media_url, media_type, agent_state, timestamp`
- **knowledge_docs** — `tenant_id, doc_type, title, content` (RAG source of truth; embedded into Chroma on boot)
- **catalog_items** — `tenant_id, name, price, image_url, ai_description, attributes`
- **customer_routing** — `customer_phone → tenant_id` (unique)
- **processed_webhooks** — `whatsapp_message_id` (unique; webhook idempotency)

---

## Environment Variables (.env)

```bash
# MongoDB
MONGO_URI=mongodb+srv://USER:PASS@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=whatsapp_agent

# Meta WhatsApp Cloud API
META_PHONE_NUMBER_ID=your_phone_number_id
META_ACCESS_TOKEN=your_access_token          # permanent System User token in production
META_VERIFY_TOKEN=any_string_you_choose
META_APP_SECRET=your_app_secret              # enables X-Hub-Signature-256 validation

# LLM
GROQ_API_KEY=your_groq_key                   # console.groq.com (primary, tool calling)
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_API_KEY=your_gemini_key               # aistudio.google.com (vision)
GEMINI_MODEL=gemini-2.0-flash

# App / auth
APP_BASE_URL=https://your-backend.up.railway.app
ADMIN_PASSWORD=choose_a_password
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
On startup the app connects to MongoDB, seeds the 2 demo tenants + knowledge (if empty), and builds the Chroma RAG index. API docs at http://localhost:8000/docs.

### Expose the webhook (ngrok)
```bash
ngrok http 8000
# set APP_BASE_URL to the https ngrok URL, restart backend
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

### Backend → Railway
1. Push to GitHub → Railway → New → Deploy from repo → Root: `backend`, Docker.
2. Add all env vars. Set the healthcheck path to `/health`.
3. Deploy → note your `https://<app>.up.railway.app` URL.

### Frontend → Vercel
1. Vercel → New Project → import repo → Root: `frontend`, framework: Vite.
2. Env: `VITE_API_BASE_URL=https://<app>.up.railway.app`.
3. Deploy.

### Meta Webhook
- Callback URL: `https://<app>.up.railway.app/api/webhooks/whatsapp`
- Verify token: your `META_VERIFY_TOKEN`; subscribe to the `messages` field.

---

## Features

### Core (assignment Tasks 1–6)
- Multi-tenant DB schema with full isolation
- WhatsApp read receipts, native typing indicator, `*bold*`/`_italics_`, image & document sending
- LangGraph 4-node agent
- Async webhook — returns 200 OK in <1s, runs the agent in the background
- Dashboard: tenant switcher, live chat monitor (image thumbnails, PDF badges, typing indicator, escalation in red), broadcast drawer
- Containerized + cloud deployed

### Bonus
- **Webhook security** — X-Hub-Signature-256 HMAC validation (enforced when `META_APP_SECRET` set)
- **Inbound media parsing** — customer-sent images described by Gemini Vision and fed into the conversation
- **Fallback handover** — frustration → `NEEDS_HUMAN`, auto-replies halt, chat highlighted red

### Reliability
- **Webhook idempotency** — unique index on `whatsapp_message_id`
- **Atomic session creation** — `find_one_and_update(upsert)`
- **Rate-limit resilience** — Groq retry/backoff; Gemini for vision
- **Tenant-filtered RAG** — every Chroma query scoped by `tenant_id`

---

## Notes & Limitations
- Demo uses one Meta **test number** shared by both tenants. In production each tenant maps to its own `phone_number_id` and routing is fully deterministic.
- Broadcast uses free-form text (Meta only allows this inside the 24-hour customer-service window; production broadcasts use approved templates).
- ChromaDB is in-memory and rebuilds from MongoDB on each restart (a managed vector DB would be used at larger scale).
