# Confirmation Checkpoints — Do Not Skip Any

These are the exact things the evaluator will check from the PDF.
Verify each one with a real test before marking done.

---

## C1 — 200 OK Returns BEFORE LangGraph Starts
**From PDF:** "The webhook must immediately return 200 OK to Meta within 3 seconds"

**How to verify:**
1. Send a WhatsApp message
2. In Meta Developer Dashboard → Webhook Logs → check delivery time
3. Should show 200 OK delivered in < 500ms
4. Bot reply should arrive 2-5 seconds LATER (after LangGraph finishes)

**Code check:**
```python
background_tasks.add_task(run_agent, message_data)
return Response(status_code=200)   # THIS LINE EXECUTES FIRST
# run_agent() starts AFTER this line
```

---

## C2 — Typing Indicator Fires BEFORE LLM Call
**From PDF:** "toggle WhatsApp's native typing indicators while thinking to reduce user drop-offs"

**How to verify:**
1. Send a WhatsApp message
2. Within 1 second: typing bubble appears on YOUR phone screen
3. 2-4 seconds later: bot reply appears

**Code check:**
Typing indicator must be called in Node 1 (Acknowledge), NOT Node 3 (LLM Reasoning).
Node 1 fires before LLM is even invoked.

---

## C3 — Typing Indicator Extinguishes After Reply
**From PDF:** "automatically extinguishing the typing indicator"

**How to verify:**
After bot sends its reply, the typing bubble disappears.

**Note:** This is AUTOMATIC. Meta's typing indicator:
- Auto-stops after ~25 seconds
- Auto-stops when any message is sent from the business number

No extra API call needed to stop it.

---

## C4 — Exactly Last 5 Messages in Chat History
**From PDF:** "the last 5 messages of chat history from the database"

**Code check:**
```python
messages = await db.message_audit_log.find(
    {"session_id": state["session_id"]}
).sort("timestamp", -1).limit(5).to_list(5)  # LIMIT 5 — not 10, not all
```

---

## C5 — GET Webhook Returns hub.challenge
**From PDF:** "a GET verification endpoint (for Meta's Webhook verification challenge)"

**How to verify:**
After setting webhook URL in Meta dashboard, click "Verify and Save".
Should show green "Verified" checkmark.

**Code check:**
```python
if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
    return PlainTextResponse(content=hub_challenge)  # exact challenge string
```

---

## C6 — Document Messages Include Filename
**From PDF:** "Document Messages ('type': 'document' containing a public URL and a filename)"

**How to verify:**
Send a PDF to WhatsApp — check that filename appears (e.g., "Furniture_Catalog_2024.pdf")

**Code check:**
```python
"document": {
    "link": doc_url,
    "filename": filename   # REQUIRED — missing this = evaluator fails you
}
```

---

## C7 — Text Supports *bold* and _italics_
**From PDF:** "Regular Text Messages (supporting Markdown formatting like *bold* and _italics_)"

**How to verify:**
Bot sends a reply containing `*bold word*` → appears as **bold** in WhatsApp.
Bot sends a reply containing `_italic word_` → appears as _italic_ in WhatsApp.

WhatsApp renders this natively — no extra code needed.
Just make sure the bot's reply text includes these where appropriate.

Update tenant system prompts to encourage use:
```
"Format important product names in *bold* and prices in _italics_ where appropriate."
```

---

## C8 — Media Library is Pre-Seeded
**From PDF:** "a Media Library (pre-seeded URLs mapping query terms to assets)"

**How to verify:**
In MongoDB Atlas, open the `tenants` collection.
Each tenant document has `media_library` field with URL values.

**Code check:**
Seed script runs at startup. Media library is NOT uploaded at runtime.
```python
"media_library": {
    "catalog": "https://yourapp.onrender.com/static/furniture_catalog.pdf",
    "sofa": "https://yourapp.onrender.com/static/sofa.jpg"
}
```

---

## C9 — All 4 Session Statuses Work
**From PDF:** "WAITING_FOR_BOT, AGENT_RESPONDING, RESOLVED" + "NEEDS_HUMAN" (bonus B3)

| Status | When Set | Where |
|--------|---------|-------|
| WAITING_FOR_BOT | New session created | Session creation |
| AGENT_RESPONDING | Node 1 fires | Acknowledge Node |
| RESOLVED | Node 4 completes | Dispatcher Node |
| NEEDS_HUMAN | Frustration detected | LLM Reasoning Node |

**How to verify:**
After sending a message, check MongoDB `chat_sessions.status` — should transition correctly.

---

## C10 — Chroma Always Filters by tenant_id
**Purpose:** Prevent Tenant A's data from appearing in Tenant B's bot answers

**Code check:**
```python
results = collection.query(
    query_texts=[query],
    where={"tenant_id": tenant_id},   # THIS MUST ALWAYS BE PRESENT
    n_results=3
)
```

**Test:**
Ask Tenant B's bot about "Milano Sofa" (Tenant A product).
Bot should say it doesn't know this product, NOT describe it.

---

## C11 — Static Files Have Real HTTPS URLs
**Why:** Meta API downloads media from your URL. Localhost URLs fail.

**How to verify after deploy:**
1. Open `https://yourapp.onrender.com/static/sofa.jpg` in browser — must load
2. Open `https://yourapp.onrender.com/static/furniture_catalog.pdf` in browser — must load
3. Send catalog to WhatsApp → customer receives downloadable PDF

---

## C12 — Broadcast Drawer Exists in Frontend
**From PDF:** "Broadcast Campaign Drawer: An interface allowing administrators to select a cohort
and trigger a predefined template message broadcast"

**How to verify:**
Dashboard has a "Broadcast" button/panel.
Can select multiple phone numbers.
Can choose a template message.
Can click Send → numbers receive WhatsApp messages.

---

## C13 — Chat Thread Shows 3 Visual Types
**From PDF:** "chat thread showing: User text messages. Bot messages with visual indicators
for sent images or downloadable PDF badges. Metadata indicators showing when bot was in typing state"

**How to verify in UI:**
- [ ] Text message: plain text bubble
- [ ] Image message: inline thumbnail image in bubble
- [ ] Document message: PDF icon + filename + download link
- [ ] Typing state: metadata row "🤖 Bot was in typing state at HH:MM"

---

## Summary Checklist (Print This Out)

```
Pre-build:    [ ] All 8 accounts + credentials ready
Phase 1:      [ ] Project scaffolds + both servers start
Phase 2A:     [ ] MongoDB models + indexes created
Phase 2B:     [ ] Tenant A + B seeded in Atlas
Phase 2C:     [ ] Chroma RAG rebuilt correctly on startup
Phase 3:      [ ] All 5 WhatsApp methods tested manually
Phase 3B:     [ ] Static files load at localhost URL
Phase 4A-4G:  [ ] Full LangGraph pipeline works end-to-end
Phase 5A:     [ ] Meta webhook verified (green checkmark)
Phase 5B:     [ ] 200 OK returned < 500ms (check Meta logs)
Phase 5C:     [ ] All dashboard API endpoints return data
Phase 6:      [ ] Frontend loads with all 3 panels + broadcast
Phase 7A:     [ ] Fake webhook POST returns 403
Phase 7B:     [ ] Send image to bot → bot describes it
Phase 7C:     [ ] Frustration message → red session in dashboard
Phase 8:      [ ] Render deploy live, Vercel deploy live
Phase 8:      [ ] Meta webhook points to Render URL (verified)
Phase 8:      [ ] UptimeRobot pinging /health every 5 min
Phase 9:      [ ] README written, code on GitHub, demo recorded
```
