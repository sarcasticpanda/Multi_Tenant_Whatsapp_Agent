# Requirements Checklist — Asked (PDF) vs Delivered

## EXACT PDF QUOTES vs WHAT WE BUILT

### Task 5: Lightweight Frontend Dashboard — VERBATIM from PDF:
> "Build a simple, responsive dashboard (React, Vue, or plain HTML/Tailwind CSS) for
> business owners to audit their agent's work:
> - **Tenant Switcher**: Easily toggle between viewing Tenant A and Tenant B.
> - **Live Chat Monitor**: A list of active phone numbers conversing with the bot.
>   Selecting a number displays a stylized chat thread showing:
>     - User text messages.
>     - Bot messages with visual indicators for sent images or downloadable PDF badges.
>     - Metadata indicators showing when the bot was in the 'typing...' state.
> - **Broadcast Campaign Drawer**: An interface allowing administrators to select a cohort
>   and trigger a predefined template message broadcast (e.g., 'Send New Catalog Promo')
>   to targeted numbers."

| PDF asks for | Built? | Notes |
|--------------|--------|-------|
| Tenant Switcher (toggle A/B) | ✅ YES | TenantSwitcher.jsx |
| Live Chat Monitor (list of phone numbers) | ✅ YES | ChatMonitor.jsx |
| Stylized chat thread - user text | ✅ YES | ChatThread.jsx |
| Bot image indicators | ✅ YES | inline thumbnails |
| Downloadable PDF badges | ✅ YES | PDF badge w/ link |
| "typing..." metadata indicator | ✅ YES | "🤖 bot was typing" |
| Broadcast Campaign Drawer | ✅ YES | needs valid token + template |

### What the PDF DOES NOT ask for (so we correctly did NOT build):
| Feature you mentioned | In PDF? | Verdict |
|----------------------|---------|---------|
| Login / signup page | ❌ NOT in PDF | Not required |
| Customer management page | ❌ NOT in PDF | Not required |
| Tenant management UI | ❌ NOT in PDF | Tenants are "pre-seeded" per Task 1 |
| Document/image upload page | ❌ NOT in PDF | Media library is "pre-seeded URLs" per Task 1 |

**PDF Task 1 verbatim:** "a Media Library (**pre-seeded URLs** mapping query terms to assets)".
The word "pre-seeded" means we seed them in code/DB — NO upload UI is required by the assignment.

---

## FULL ASSIGNMENT CHECKLIST

### Task 1: Multi-Tenant Database
| Requirement | Status |
|-------------|--------|
| Tenant: id, name, prompt directions, media library | ✅ |
| Customer Interaction: phone, tenant_id, status (WAITING/RESPONDING/RESOLVED), context vars | ✅ |
| Message Audit Log: timestamp, sender, text, media URLs/mimetypes | ✅ |

### Task 2: WhatsApp Cloud API
| Requirement | Status |
|-------------|--------|
| Read receipts | ✅ live |
| Typing indicator | ✅ live (fixed to message_id format) |
| Text messages (*bold* _italics_) | ✅ live |
| Image messages (public URL) | ✅ live |
| Document messages (URL + filename) | ✅ live |

### Task 3: LangGraph Orchestration
| Node | Status |
|------|--------|
| Acknowledge (read + typing + save PENDING) | ✅ |
| Context Retriever (prompt + media rules + last 5 msgs) | ✅ |
| LLM Reasoning (text vs tool/media decision) | ✅ |
| Dispatcher (send + save + extinguish typing) | ✅ |

### Task 4: Async Webhook
| Requirement | Status |
|-------------|--------|
| POST /api/webhooks/whatsapp | ✅ |
| GET verification challenge | ✅ verified by Meta |
| Return 200 OK < 3s, run agent in background | ✅ (BackgroundTasks) |

### Task 5: Frontend — see above, all ✅

### Task 6: Cloud Deployment
| Requirement | Status |
|-------------|--------|
| Deploy to cloud | ❌ PENDING (Render) |
| Single Dockerfile | ✅ written, not deployed |
| Env config / secrets | ✅ .env (Render env vars pending) |
| Webhook mapped to live HTTPS | ❌ currently ngrok, not cloud |

### Bonus Points
| Bonus | Status |
|-------|--------|
| B1: X-Hub-Signature-256 validation | ✅ coded |
| B2: Inbound image → multimodal LLM | ✅ coded (Gemini Vision) |
| B3: Frustration → NEEDS_HUMAN + red highlight | ✅ coded |

### Deliverables
| Item | Status |
|------|--------|
| GitHub repo | ❌ pending push |
| Live URLs (dashboard + webhook) | ❌ pending deploy |
| README (env, run, LangGraph schema, deploy) | ❌ pending |
| Demo video 3-5 min | ❌ user will record |

---

## KNOWN ISSUES TO FIX
1. **Gemini 2.5 Flash = 20 req/day free limit** → switch to gemini-2.0-flash OR add Groq fallback (URGENT)
2. **Broadcast needs valid token** + Meta template policy (free-form only works in 24h window)
3. **Access token expires ~24h** → need permanent System User token for deploy

---

## HOW MEMORY WORKS (LLM remembering a person's conversation)
- Every message (in + out) saved to MongoDB `message_audit_log` with session_id
- session_id = unique per (tenant_id + customer_phone)
- Context Retriever node pulls **last 5 messages** for that session_id
- These are injected into Gemini as conversation history
- So the bot remembers the last 5 turns per person, per tenant
- Want longer memory? Increase the limit (currently 5 per PDF spec) or add summary memory

## HOW DATA STORAGE WORKS
- Tenant config + media library → MongoDB `tenants`
- Knowledge (products/FAQs) text → MongoDB `knowledge_docs` → embedded into Chroma at startup
- Conversations → MongoDB `chat_sessions` + `message_audit_log`
- Uploaded files (current) → static folder in repo, served at /static/<file>
- Future upload feature → would save file to /static + add URL to tenant.media_library (see docs/10)
