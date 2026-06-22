# What's Left — Master Roadmap

Last updated: live during build.

## DONE ✅

| # | Item | Verified? |
|---|------|-----------|
| 1 | Project scaffold + venv (isolated, no conflicts) | YES |
| 2 | MongoDB schema (tenants, chat_sessions, message_audit_log, knowledge_docs) | YES |
| 3 | 2 tenants seeded (Lumière Furniture "Aria", AutoCare "Max") | YES |
| 4 | 18 knowledge docs seeded (products, FAQs, pricing, contact) | YES |
| 5 | Chroma RAG with tenant isolation | YES (tested) |
| 6 | WhatsApp client (read receipt, typing, text, image, document) | YES (live) |
| 7 | Typing indicator (fixed to message_id format) | YES (200 OK) |
| 8 | LangGraph 4-node pipeline | YES (live) |
| 9 | Gemini 2.5 Flash + tool calling (get_media, search_knowledge, escalate) | YES |
| 10 | Two-step function calling (natural captions, no robotic text) | YES |
| 11 | Media-aware prompt (bot knows exactly what files it has) | YES |
| 12 | Async webhook (200 OK instant, background LangGraph) | YES (live) |
| 13 | Webhook GET verification (Meta connected) | YES (verified) |
| 14 | Bonus B1: X-Hub-Signature-256 validation | CODED |
| 15 | Bonus B2: inbound image → Gemini Vision | CODED |
| 16 | Bonus B3: frustration → NEEDS_HUMAN handover | CODED |
| 17 | Dashboard REST API (tenants, sessions, messages, broadcast) | CODED |
| 18 | ngrok tunnel + Meta webhook live | YES |
| 19 | End-to-end real WhatsApp test (text + PDF + image) | YES (on phone) |

## REMAINING ❌ — In Order

### NEXT: Phase 6 — Frontend Dashboard
- [ ] React + Vite + Tailwind setup
- [ ] TenantSwitcher (toggle Tenant A / B)
- [ ] ChatMonitor (list active phone numbers + status badges)
- [ ] ChatThread (user/bot bubbles, image thumbnails, PDF badges, typing metadata, NEEDS_HUMAN red)
- [ ] BroadcastDrawer (select numbers, template, send)
- [ ] api/client.js (connect to backend)
- [ ] Poll sessions every 5s for live updates

### THEN: Enhancement — Multimodal Catalog Pipeline (OPTIONAL)
- [ ] See docs/10_MULTIMODAL_CATALOG_PIPELINE.md
- [ ] Build ONLY if time remains after deploy
- [ ] PDF → extract images → Gemini Vision describe → store → RAG-searchable

### THEN: Phase 8 — Deployment
- [ ] Dockerfile (already written, needs PyMuPDF if pipeline built)
- [ ] Deploy backend to Render
- [ ] Permanent Meta token (System User) so it doesn't expire
- [ ] Deploy frontend to Vercel
- [ ] Point Meta webhook to Render URL
- [ ] UptimeRobot keep-alive

### THEN: Phase 9 — Deliverables
- [ ] README.md (env setup, local run, LangGraph schema, deployment docs)
- [ ] Push to GitHub
- [ ] Demo video (3-5 min): Tenant A dashboard → send msg → typing → reply with catalog/image
      → switch Tenant B → different answers → show state/logs changing

## AGREED ORDER
```
1. (now) Frontend dashboard
2. Multimodal catalog pipeline  [only if time]
3. Deploy (Render + Vercel)
4. README
5. Demo video
```

## KNOWN ITEMS TO REMEMBER
- Meta temporary token expires ~24h → must get permanent System User token before final demo
- ngrok URL changes each restart → if ngrok restarts, update APP_BASE_URL + re-seed tenants + re-point Meta webhook
- Render free tier has no persistent disk → Chroma rebuilds from MongoDB on startup (already handled)
- Both tenants share one test phone number (sandbox limit) → fine for demo
