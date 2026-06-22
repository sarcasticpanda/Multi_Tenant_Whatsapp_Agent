# Master TODO Checklist — Build Order

Complete each section fully before moving to the next.
Do NOT skip ahead. Each section depends on the previous.

---

## PRE-BUILD: Accounts & Credentials Setup
*(Do this FIRST before writing any code)*

- [ ] Create MongoDB Atlas account → create M0 free cluster → get MONGO_URI
- [ ] Create Meta Developer account → create App → add WhatsApp product → note PHONE_NUMBER_ID + ACCESS_TOKEN
- [ ] Create Google AI Studio account → generate GEMINI_API_KEY (free)
- [ ] Create Groq account → generate GROQ_API_KEY (free)
- [ ] Create Render.com account (free)
- [ ] Create Vercel account (free)
- [ ] Create UptimeRobot account (free)
- [ ] Add your personal WhatsApp number as test recipient in Meta Dashboard

---

## PHASE 1 — Project Scaffolding

- [ ] Create folder structure:
  ```
  Multi_Tenant_Whatsapp_Agent/
  ├── backend/
  │   ├── app/
  │   │   ├── db/
  │   │   ├── rag/
  │   │   ├── api/
  │   │   ├── whatsapp/
  │   │   └── agent/
  │   └── static/
  ├── frontend/
  │   └── src/components/
  └── docs/
  ```
- [ ] Create `backend/requirements.txt`
- [ ] Create `backend/.env.example`
- [ ] Create `backend/app/config.py` (pydantic-settings for all env vars)
- [ ] Init React+Vite frontend: `npm create vite@latest frontend -- --template react`
- [ ] Install Tailwind CSS in frontend
- [ ] Create `docker-compose.yml` for local dev
- [ ] Add `.gitignore` (include .env, chroma_store/, __pycache__, node_modules)

**CONFIRM BEFORE MOVING ON:**
- [ ] `python -m uvicorn app.main:app --reload` starts without errors
- [ ] `npm run dev` starts frontend without errors

---

## PHASE 2A — MongoDB Models

- [ ] `app/db/mongodb.py` — Motor async client, connect/disconnect functions
- [ ] `app/db/models.py` — Pydantic models:
  - [ ] `TenantModel` (tenant_id, name, system_prompt, phone_number_id, media_library, is_active)
  - [ ] `ChatSessionModel` (session_id, tenant_id, customer_phone, status, context_vars, message_count, last_message_at)
  - [ ] `MessageAuditLogModel` (message_id, whatsapp_message_id, session_id, tenant_id, direction, sender, text_content, media_url, media_type, media_mime_type, agent_state, is_read, timestamp)
  - [ ] `KnowledgeDocModel` (doc_id, tenant_id, doc_type, title, content, source)
- [ ] Create MongoDB indexes (see 02_DATABASE_DESIGN.md for full list)

**CONFIRM BEFORE MOVING ON:**
- [ ] Can insert and fetch a test document from MongoDB Atlas
- [ ] All 4 collections exist in Atlas dashboard

---

## PHASE 2B — Seed Data

- [ ] `app/db/seed.py` — seeds 2 tenants if collection is empty:
  - [ ] Tenant A: Luxury Furniture Store (system_prompt + full media_library with 5 keywords)
  - [ ] Tenant B: AutoCare Services (system_prompt + full media_library with 4 keywords)
- [ ] Seed is called at FastAPI startup if tenants collection is empty

**CONFIRM BEFORE MOVING ON:**
- [ ] Run seed manually — both tenants appear in MongoDB Atlas
- [ ] media_library URLs point to correct static file paths

---

## PHASE 2C — Chroma RAG Setup

- [ ] `app/rag/embedder.py` — sentence-transformers wrapper (all-MiniLM-L6-v2)
- [ ] `app/rag/chroma_client.py`:
  - [ ] `build_chroma_index()` — fetch knowledge_docs from MongoDB → embed → load to Chroma (in-memory)
  - [ ] `search_knowledge_base(query, tenant_id)` — search with tenant_id filter + similarity threshold
- [ ] `app/rag/seed_knowledge.py` — insert all knowledge docs for Tenant A + B into MongoDB knowledge_docs collection
- [ ] Call `build_chroma_index()` in FastAPI startup event

**CONFIRM BEFORE MOVING ON:**
- [ ] `search_knowledge_base("leather sofa", "tenant_a")` returns relevant chunks
- [ ] `search_knowledge_base("sofa", "tenant_b")` returns empty (cross-tenant isolation works)
- [ ] Chroma rebuild takes < 30 seconds on startup

---

## PHASE 3 — WhatsApp API Client

- [ ] `app/whatsapp/client.py`:
  - [ ] `send_read_receipt(phone_number_id, message_id)` — marks message as read
  - [ ] `send_typing_indicator(phone_number_id, to)` — shows typing bubble [EXACT PAYLOAD FROM PDF]
  - [ ] `send_text_message(phone_number_id, to, text)` — supports *bold* _italics_
  - [ ] `send_image_message(phone_number_id, to, image_url)` — type:image
  - [ ] `send_document_message(phone_number_id, to, doc_url, filename)` — type:document WITH filename
  - [ ] `get_media_url(media_id)` — converts Meta media_id to downloadable URL (bonus B2)
  - [ ] `_post(phone_number_id, payload)` — internal httpx async helper

**CONFIRM BEFORE MOVING ON:**
- [ ] Send a test text message to your WhatsApp number and receive it
- [ ] Send a test document — confirm filename appears in WhatsApp
- [ ] Send a test image — confirm it displays in WhatsApp
- [ ] Typing indicator appears on your phone for 25 seconds

---

## PHASE 3B — Static Assets

- [ ] Download and save to `backend/static/`:
  - [ ] `furniture_catalog.pdf` (any sample PDF, rename it)
  - [ ] `sofa.jpg` (from Unsplash)
  - [ ] `showroom.png` (from Unsplash)
  - [ ] `price_list.pdf` (copy of furniture_catalog.pdf is fine)
  - [ ] `invoice_template.pdf` (any invoice sample PDF)
  - [ ] `repair_diagram.jpg` (from Unsplash: car engine)
- [ ] Mount static files in FastAPI: `app.mount("/static", StaticFiles(...))`

**CONFIRM BEFORE MOVING ON:**
- [ ] `http://localhost:8000/static/sofa.jpg` loads in browser
- [ ] `http://localhost:8000/static/furniture_catalog.pdf` loads in browser
- [ ] WhatsApp can actually deliver these (needs HTTPS — test after deploy)

---

## PHASE 4A — LangGraph State Schema

- [ ] `app/agent/state.py` — `AgentState` TypedDict with all fields:
  - tenant_id, customer_phone, session_id, whatsapp_message_id
  - inbound_text, inbound_media_url, inbound_media_type, inbound_image_description
  - tenant_config, chat_history, rag_chunks
  - llm_reply, media_to_send, media_type, media_filename
  - session_status, error

**CONFIRM BEFORE MOVING ON:**
- [ ] TypedDict imports without errors
- [ ] Can create an instance with all required fields

---

## PHASE 4B — Tool Definitions

- [ ] `app/agent/tools.py` — 3 Gemini function definitions:
  - [ ] `get_media(keyword)` — look up tenant media_library
  - [ ] `search_knowledge(query)` — additional RAG search
  - [ ] `escalate_to_human(reason)` — frustration handover

---

## PHASE 4C — Node 1: Acknowledge

- [ ] `acknowledge_node` in `app/agent/nodes.py`:
  - [ ] Call `send_read_receipt()` ← fires FIRST
  - [ ] Call `send_typing_indicator()` ← fires SECOND (before any processing)
  - [ ] Insert inbound message into `message_audit_log` with `agent_state: "TYPING"`
  - [ ] Update `chat_sessions.status` to `"AGENT_RESPONDING"`

**CONFIRM BEFORE MOVING ON:**
- [ ] After calling this node, blue ticks appear on sender's WhatsApp
- [ ] Typing bubble appears on sender's WhatsApp
- [ ] Message appears in MongoDB message_audit_log

---

## PHASE 4D — Node 2: Context Retriever

- [ ] `context_retriever_node` in `app/agent/nodes.py`:
  - [ ] Fetch tenant from MongoDB by tenant_id
  - [ ] Fetch last 5 messages from message_audit_log (sorted by timestamp DESC, reversed to ASC)
  - [ ] Call `search_knowledge_base(user_message, tenant_id)` → rag_chunks
  - [ ] BONUS B2: If inbound_media_url exists → call Gemini Vision → set inbound_image_description

**CONFIRM BEFORE MOVING ON:**
- [ ] State has tenant_config populated
- [ ] State has exactly ≤ 5 chat_history messages
- [ ] State has rag_chunks (can be empty list — that's ok)

---

## PHASE 4E — Node 3: LLM Reasoning

- [ ] `llm_reasoning_node` in `app/agent/nodes.py`:
  - [ ] Build system prompt (tenant prompt + RAG chunks)
  - [ ] Build conversation history for Gemini
  - [ ] Call `gemini-2.5-flash` with function calling
  - [ ] Handle `get_media` tool call → resolve URL from media_library
  - [ ] Handle `escalate_to_human` tool call → set NEEDS_HUMAN status
  - [ ] Extract final text reply
  - [ ] Set media_to_send, media_type, media_filename in state

**CONFIRM BEFORE MOVING ON:**
- [ ] "show me your catalog" → LLM calls get_media("catalog") → media_to_send is set
- [ ] "I'm frustrated, this is terrible service" → escalate_to_human called → status is NEEDS_HUMAN
- [ ] General question → just text reply, no media

---

## PHASE 4F — Node 4: Dispatcher

- [ ] `dispatcher_node` in `app/agent/nodes.py`:
  - [ ] `send_text_message()` always
  - [ ] If IMAGE: `send_image_message()`
  - [ ] If DOCUMENT: `send_document_message()` with filename
  - [ ] Insert outbound message into `message_audit_log` with `agent_state: "SENT"`
  - [ ] Update `chat_sessions.status` to `"RESOLVED"` (or keep `"NEEDS_HUMAN"`)
  - [ ] Increment `message_count` by 2 (inbound + outbound)

**CONFIRM BEFORE MOVING ON:**
- [ ] Customer receives text reply on WhatsApp
- [ ] If catalog requested: customer receives PDF attachment in WhatsApp
- [ ] Outbound message appears in MongoDB with direction: OUTBOUND

---

## PHASE 4G — Compile LangGraph Graph

- [ ] `app/agent/graph.py`:
  - [ ] `StateGraph(AgentState)`
  - [ ] Add 4 nodes
  - [ ] Set entry point to `acknowledge`
  - [ ] Add edges: acknowledge → retrieve → reason → dispatch → END
  - [ ] Compile: `agent_graph = graph.compile()`
- [ ] Test: `await agent_graph.ainvoke(mock_state)` runs all 4 nodes

**CONFIRM BEFORE MOVING ON:**
- [ ] Full end-to-end pipeline runs without errors on mock data
- [ ] WhatsApp receives reply when graph runs

---

## PHASE 5A — Webhook GET (Meta Verification)

- [ ] `app/api/webhooks.py` — GET handler:
  - [ ] Validate `hub.mode == "subscribe"`
  - [ ] Validate `hub.verify_token == settings.META_VERIFY_TOKEN`
  - [ ] Return `hub.challenge` as plain text response

**CONFIRM BEFORE MOVING ON:**
- [ ] Meta shows "Verified" after you click Save in their dashboard

---

## PHASE 5B — Webhook POST (Async Handler)

- [ ] POST handler in `app/api/webhooks.py`:
  - [ ] BONUS B1: Validate X-Hub-Signature-256 header FIRST
  - [ ] Parse payload with `extract_message()`
  - [ ] If None (status update): return 200 immediately
  - [ ] Look up or create chat_session in MongoDB
  - [ ] If session.status == NEEDS_HUMAN: log message only, return 200
  - [ ] Add `run_agent(message_data)` to `background_tasks`
  - [ ] `return Response(status_code=200)` ← THIS MUST BE BEFORE LangGraph RUNS

**CONFIRM BEFORE MOVING ON:**
- [ ] Meta receives 200 OK in < 500ms (check Meta webhook delivery logs)
- [ ] LangGraph runs in background AFTER 200 is returned
- [ ] Send test message — receive bot reply

---

## PHASE 5C — Dashboard API

- [ ] `app/api/dashboard.py`:
  - [ ] `GET /api/tenants` → list all tenants
  - [ ] `GET /api/tenants/{tenant_id}/sessions` → sessions for tenant, sorted by last_message_at DESC
  - [ ] `GET /api/sessions/{session_id}/messages` → all messages in session
  - [ ] `POST /api/broadcast` → send template text message to list of phone numbers

**CONFIRM BEFORE MOVING ON:**
- [ ] All endpoints return correct data
- [ ] `/api/tenants` returns Tenant A and Tenant B
- [ ] After a test conversation, `/api/sessions/{id}/messages` shows both INBOUND and OUTBOUND

---

## PHASE 6 — Frontend Dashboard

### TenantSwitcher.jsx
- [ ] Shows two tenant cards (Tenant A / Tenant B)
- [ ] Clicking switches active tenant, fetches sessions
- [ ] Highlights active tenant

### ChatMonitor.jsx
- [ ] Lists active sessions (phone numbers) for selected tenant
- [ ] Shows session status badge (AGENT_RESPONDING, RESOLVED, NEEDS_HUMAN in red)
- [ ] Clicking a session opens ChatThread
- [ ] Polls `/api/tenants/{id}/sessions` every 5 seconds

### ChatThread.jsx
- [ ] User messages: right-aligned, grey bubble
- [ ] Bot messages: left-aligned, white/blue bubble
- [ ] Image messages: shows inline thumbnail
- [ ] Document messages: shows PDF icon with filename + download link
- [ ] Typing metadata: if message has `agent_state: "TYPING"` → show "🤖 Bot was typing..."
- [ ] NEEDS_HUMAN sessions: entire chat border turns RED

### BroadcastDrawer.jsx
- [ ] Slide-in panel on right side
- [ ] Checkbox list of customer phone numbers
- [ ] Dropdown: choose template message
- [ ] "Send Broadcast" button → POST /api/broadcast
- [ ] Success/error toast

### api/client.js
- [ ] Fetch wrapper with base URL from env

**CONFIRM BEFORE MOVING ON:**
- [ ] Can see both tenants in dashboard
- [ ] Can see chat thread of test conversation (all messages)
- [ ] Images show as thumbnails, PDFs show as download badges
- [ ] Switching tenants shows different sessions
- [ ] Broadcast sends correctly

---

## PHASE 7 — All Bonus Points

### B1: Webhook Signature Validation
- [ ] `verify_webhook_signature(payload_bytes, signature_header)` in `app/whatsapp/client.py`
- [ ] HMAC-SHA256 with META_APP_SECRET
- [ ] Called in POST webhook handler BEFORE anything else
- [ ] Returns 403 if invalid

**CONFIRM:** Fake POST to webhook returns 403. Real Meta webhook still works.

### B2: Inbound Image Analysis
- [ ] In webhook parser: detect `type == "image"` → extract `media_id`
- [ ] In context_retriever_node: if `inbound_media_url` exists:
  - [ ] Call `get_media_url(media_id)` → get temp URL
  - [ ] Download image bytes
  - [ ] Send to Gemini Vision → get description
  - [ ] Store in `inbound_image_description`
- [ ] In llm_reasoning_node: prepend description to user message

**CONFIRM:** Send image of a sofa → bot describes it + relates to product catalog

### B3: Frustration Detection + Human Handover
- [ ] `escalate_to_human` tool defined with clear trigger description
- [ ] When called: set `session_status = "NEEDS_HUMAN"` in state
- [ ] In dispatcher: if NEEDS_HUMAN → send empathy message + stop processing
- [ ] In webhook handler: if session.status == NEEDS_HUMAN → skip LangGraph for future messages
- [ ] In ChatThread.jsx: NEEDS_HUMAN session highlighted in red

**CONFIRM:**
- [ ] "This is terrible, I've been waiting 2 weeks and nothing" → bot escalates, no further auto-reply
- [ ] Session shows red in dashboard

---

## PHASE 8 — Deployment

- [ ] Write `backend/Dockerfile` (see 06_DEPLOYMENT.md)
- [ ] Add model download step in Dockerfile (sentence-transformers at build time)
- [ ] Test Dockerfile locally: `docker build -t backend . && docker run -p 8000:8000 backend`
- [ ] Deploy backend to Render (see step-by-step in 06_DEPLOYMENT.md)
- [ ] Set all env vars in Render dashboard
- [ ] Confirm `https://xxx.onrender.com/health` returns `{"status": "ok"}`
- [ ] Configure Meta webhook URL to Render URL → verify successfully
- [ ] Deploy frontend to Vercel → set VITE_API_BASE_URL
- [ ] Setup UptimeRobot monitor (ping every 5 min)

**CONFIRM:**
- [ ] Send real WhatsApp message → receive bot reply (full cloud flow)
- [ ] Dashboard loads on Vercel URL
- [ ] Dashboard shows conversation from cloud test

---

## PHASE 9 — Deliverables

- [ ] Write `README.md` (env vars, local run, LangGraph schema, deployment)
- [ ] Push all code to GitHub (public repo)
- [ ] Record Loom demo video (3-5 minutes):
  - [ ] Show Tenant A dashboard on Vercel
  - [ ] Send WhatsApp message → show typing on phone
  - [ ] Bot replies with text + PDF/image
  - [ ] Switch to Tenant B → different bot personality
  - [ ] Show message_audit_log updating in MongoDB Atlas
- [ ] Final repo link + deployed URLs ready

---

## Requirements.txt (Backend)

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
motor==3.5.0             # async MongoDB driver
pydantic-settings==2.4.0
httpx==0.27.0            # async HTTP for Meta API calls
langgraph==0.2.0
langchain-core==0.3.0
google-generativeai==0.8.0   # Gemini 2.5 Flash
groq==0.11.0             # Groq fallback
sentence-transformers==3.1.0  # embeddings
chromadb==0.5.0          # vector store
pypdf==4.3.0             # PDF text extraction
python-multipart==0.0.9
python-dotenv==1.0.0
```
