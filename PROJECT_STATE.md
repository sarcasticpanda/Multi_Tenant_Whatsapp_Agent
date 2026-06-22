# Project State — Multi-Tenant WhatsApp AI Agent (KredAI assignment)

> Single source of truth for everything built, deployed, and remaining.
> Last updated mid-build (June 2026).

---

## 1. WHAT IS DEPLOYED (live)

| Piece | Where | URL / detail |
|-------|-------|--------------|
| **Backend** (FastAPI) | Railway (Docker) | https://whatsapp-agent-backend-production-3f9e.up.railway.app |
| **Database** | MongoDB Atlas (cluster: ClusterTest) | db name: `whatsapp_agent` |
| **File storage** | MongoDB GridFS (inside Atlas) | served at `/files/{id}` |
| **WhatsApp** | Meta Cloud API, test number +1 555 650 7603 | phone_number_id 1095181447021644 |
| **Dashboard** (React) | Vercel | https://multi-tenant-whatsapp-agent.vercel.app (login: kredai_admin) — env VITE_API_BASE_URL → Railway |
| **GitHub** | sarcasticpanda/Multi_Tenant_Whatsapp_Agent | branch main |

**Meta token:** System-User token, expires ~Aug 2026 (good for evaluation). Lives in Railway env `META_ACCESS_TOKEN`.

---

## 2. TECH STACK & WHY

| Layer | Choice | Notes |
|-------|--------|-------|
| Backend | FastAPI (Python 3.11) | async, LangGraph-native |
| Agent | LangGraph (4 nodes) | Acknowledge → Context → Reason → Dispatch |
| **Primary LLM** | **Groq llama-3.3-70b-versatile** | tool calling, 30 req/min free, reliable |
| **Vision LLM** | **Google Gemini 2.0 Flash** | ONLY for images (inbound photo + catalog auto-describe) |
| Embeddings (RAG) | ChromaDB built-in ONNX `all-MiniLM-L6-v2` | local, no torch, low memory |
| App DB | MongoDB Atlas M0 (free) | structured data |
| File store | MongoDB GridFS | uploads + inbound images survive restarts |
| Vector store | ChromaDB (in-memory, rebuilt from Mongo at startup, in background) | |
| Frontend | React + Vite + Tailwind | warm editorial theme (Fraunces font) |
| Deploy | Railway (backend) + Vercel (frontend, pending) | |

> NOTE: We originally planned Gemini as primary, but its free *text* quota is near-zero (hit limit 0).
> So **Groq is primary for reasoning/tools**, Gemini is used **only for vision**. ChromaDB embeddings are
> local ONNX (no API needed).

---

## 3. HOW MONGODB MANAGES DATA (collections in `whatsapp_agent`)

| Collection | Holds | Key fields |
|------------|-------|-----------|
| **tenants** | each brand | tenant_id, name, system_prompt, whatsapp_phone_number_id, media_library{keyword→URL} |
| **chat_sessions** | one per (tenant + customer phone) | session_id, tenant_id, customer_phone, status, message_count, last_message_at |
| **message_audit_log** | every message in/out | direction (INBOUND/OUTBOUND), sender, text_content, media_url, media_type, agent_state, timestamp |
| **knowledge_docs** | RAG text (FAQs, policies, pricing) | tenant_id, doc_type, title, content |
| **catalog_items** | visual products (image + data linked) | tenant_id, name, image_url, ai_description, price, attributes |
| **processed_webhooks** | webhook dedup | whatsapp_message_id (unique) — stops duplicate processing |
| **media.files / media.chunks** | GridFS file storage | uploaded + inbound images/PDFs |

**Tenant isolation:** every query is scoped by `tenant_id`. Sessions are unique per (tenant_id, customer_phone).

---

## 4. HOW RAG / CHROMA WORKS

- On startup (in a **background task** so the port binds fast), the app reads all `knowledge_docs` + `catalog_items`
  from MongoDB, embeds them with the local ONNX MiniLM model, and loads them into an in-memory Chroma collection.
- Each vector carries metadata: `tenant_id`, `type` ("knowledge" or "catalog"), and for catalog: image_url + price.
- **Three retrieval paths** (the agent's tools decide which):
  1. `get_media(keyword)` → MongoDB `media_library` → sends a fixed file (catalog PDF, invoice)
  2. `search_catalog(description)` → Chroma `type=catalog` → returns best product **image + price + details**
  3. `search_knowledge(query)` → Chroma `type=knowledge` → text answer for FAQs/policies
- Every query is filtered by `tenant_id` (no cross-tenant leakage).
- After any admin change (add/delete catalog/knowledge/tenant), the index rebuilds.

---

## 5. THE LANGGRAPH AGENT (4 nodes)

```
START → acknowledge → retrieve_context → llm_reason → dispatch → END
```
1. **acknowledge** — send WhatsApp read receipt + typing indicator, save inbound msg, status AGENT_RESPONDING
2. **retrieve_context** — load tenant cfg, last 5 messages, catalog inventory, RAG chunks; (bonus) describe inbound image via Gemini Vision + store it in GridFS
3. **llm_reason** — Groq with 4 tools (get_media, search_catalog, search_knowledge, escalate_to_human); 2-step calling for natural captions
4. **dispatch** — send text + optional image/document, save outbound, set RESOLVED (or NEEDS_HUMAN)

---

## 6. REQUIRED FEATURES (assignment Tasks 1–6) — ALL DONE

- **T1 Multi-tenant DB**: tenants / chat_sessions / message_audit_log ✅
- **T2 WhatsApp API**: read receipt, typing indicator, text (*bold*/_italics_), image, document(+filename) ✅
- **T3 LangGraph**: all 4 nodes, text-vs-media decision ✅
- **T4 Async webhook**: POST + GET verification, returns 200 in <1s, agent runs in background ✅
- **T5 Dashboard**: tenant switcher, live chat monitor (image/PDF/typing indicators), broadcast drawer ✅
- **T6 Cloud deploy**: single Dockerfile, env config, live HTTPS (Railway) ✅

## 7. BONUS FEATURES — ALL DONE

- **B1** X-Hub-Signature-256 HMAC validation (enforced) ✅
- **B2** Inbound image → Gemini Vision description + persisted to GridFS + shown in dashboard ✅
- **B3** Frustration → `escalate_to_human` → status NEEDS_HUMAN, auto-replies halt, red in dashboard ✅

## 8. EXTRA FEATURES (beyond the spec)

- **Multimodal catalog** — products link image + structured data, searchable by description
- **PDF catalog ingestion** — upload one PDF → PyMuPDF extracts every product image → Gemini Vision describes → searchable (Manage → Catalog → Import PDF)
- **Admin panel** — tenant CRUD, media-library upload, catalog/knowledge management, edit bot persona (login-gated)
- **Login gate** — password → signed HMAC token protects admin routes (ADMIN_PASSWORD)
- **GridFS storage** — uploads + customer images live in MongoDB (survive restarts)
- **Reliability**: webhook idempotency (no duplicate replies), atomic session creation, lazy LLM clients (startup never crashes), background index build (fast health check), Groq auto-retry on rate limits
- **Honesty guardrails**: bot knows its exact catalog inventory (won't present a bed as a "similar sofa"); never re-sends a file already sent in the conversation; greetings stay text-only

---

## 9. ENV VARS (set in Railway)

```
MONGO_URI, MONGO_DB_NAME, META_PHONE_NUMBER_ID, META_ACCESS_TOKEN, META_VERIFY_TOKEN,
META_APP_SECRET, GROQ_API_KEY, GROQ_MODEL, GEMINI_API_KEY, GEMINI_MODEL, ADMIN_PASSWORD, APP_BASE_URL
```
Dashboard login password: `kredai_admin`

---

## 10. KNOWN LIMITATIONS

- One shared Meta **test number** for both tenants (sandbox limit); production = one number per tenant.
- Broadcast uses free-form text (works within WhatsApp's 24h window; production needs approved templates).
- Groq free tier = 30 msgs/min (auto-retry added; send at normal pace during demo).
- ChromaDB in-memory → rebuilds (~seconds) on each Railway restart from MongoDB.

---

## 11. REMAINING WORK (agreed sequence)

1. **Deploy dashboard to Vercel** → get the live dashboard link (points at Railway backend)
2. **UI fixes** (user to specify)
3. **Add genuine tenants** with real catalogs/data via the dashboard
4. **Final LLM query tuning** — make the conversational/query handling crisp
5. **Record demo video**
6. (optional) README polish for submission

---

## 12. KEY FILES MAP

```
backend/app/
  main.py            — FastAPI app, lifespan (connect Mongo, seed, bg index build), routers, /health
  config.py          — env settings (pydantic)
  db/mongodb.py      — Motor client
  db/models.py       — Pydantic models (Tenant, ChatSession, MessageAuditLog, KnowledgeDoc, CatalogItem)
  db/seed.py         — seed tenants + ensure_indexes
  db/seed_catalog.py — seed catalog items
  rag/chroma_client.py — build index, search_knowledge_base, search_catalog
  rag/seed_knowledge.py — seed knowledge docs
  rag/pdf_extractor.py  — PDF → images + text → GridFS → catalog items
  whatsapp/client.py — Meta API (read receipt, typing, text/image/document) + signature validation
  agent/state.py     — AgentState
  agent/tools.py     — 4 tool definitions
  agent/nodes.py     — the 4 nodes + Groq/Gemini clients (lazy) + retry
  agent/graph.py     — compiled StateGraph
  api/webhooks.py    — POST/GET webhook (idempotency, signature, background agent)
  api/dashboard.py   — tenants/sessions/messages/broadcast/stats
  api/admin.py       — tenant/catalog/media/knowledge CRUD + PDF ingest (login-gated)
  api/auth.py        — login + token validation
  api/files.py       — GridFS upload + serve
frontend/src/
  App.jsx            — login gate + console/admin views, polling
  api/client.js      — fetch wrapper + auth token + displayUrl helper
  tenants.js         — per-tenant theme + status colors
  components/        — WorkspaceRail, ConversationList, ChatThread, BroadcastDrawer, StatStrip, AdminPanel, Login
```
