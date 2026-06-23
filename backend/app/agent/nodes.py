import asyncio
import base64
import json
import logging
import re
from datetime import datetime
from uuid import uuid4

from google import genai
from google.genai import types

from app.agent.state import AgentState
from app.agent.tools import TOOLS
from app.config import settings
from app.db.mongodb import get_db
from app.rag.chroma_client import search_knowledge_base, search_catalog, ensure_index_ready
from app.storage import gridfs
from app.whatsapp import client as wa

logger = logging.getLogger(__name__)

GEMINI_MODEL = settings.gemini_model

# LLM clients are created LAZILY (on first use), never at import time — so a missing
# or bad key can never crash app startup. Gemini = vision only; Groq = primary reasoning.
_gemini_client = None
_groq_client = None
_groq_init_done = False


def _get_gemini():
    global _gemini_client
    if _gemini_client is None and settings.gemini_api_key:
        try:
            _gemini_client = genai.Client(api_key=settings.gemini_api_key)
        except Exception as e:
            logger.warning(f"Gemini client unavailable: {e}")
    return _gemini_client


async def _groq_create(groq, **kwargs):
    """Groq chat completion with retry/backoff on transient rate limits (free tier).
    The Groq SDK is synchronous, so run it in a thread to NOT block the webhook server."""
    last = None
    for attempt in range(4):
        try:
            return await asyncio.to_thread(groq.chat.completions.create, **kwargs)
        except Exception as e:
            last = e
            m = str(e).lower()
            if any(w in m for w in ("rate", "429", "limit", "timeout", "temporar", "overload", "503")):
                wait = 2 * (attempt + 1)
                logger.warning(f"Groq throttled (attempt {attempt+1}): {str(e)[:120]} — retrying in {wait}s")
                await asyncio.sleep(wait)
                continue
            logger.error(f"Groq call failed (non-retryable): {str(e)[:200]}")
            raise
    raise last


def _get_groq():
    global _groq_client, _groq_init_done
    if not _groq_init_done:
        _groq_init_done = True
        if settings.groq_api_key:
            try:
                from groq import Groq
                _groq_client = Groq(api_key=settings.groq_api_key)
            except Exception as e:
                logger.warning(f"Groq client unavailable: {e}")
    return _groq_client

# Tools in OpenAI/Groq function-calling format
_groq_tools = [
    {"type": "function", "function": {
        "name": t["name"],
        "description": t["description"],
        "parameters": t["parameters"],
    }}
    for t in TOOLS
]


# ---------------------------------------------------------------------------
# Node 1: Acknowledge
# ---------------------------------------------------------------------------

async def acknowledge_node(state: AgentState) -> AgentState:
    """
    Fires read receipt + typing indicator immediately.
    Saves inbound message to MongoDB.
    """
    phone_id = state["tenant_config"]["whatsapp_phone_number_id"] if state.get("tenant_config") else settings.meta_phone_number_id

    try:
        await wa.send_read_receipt(phone_id, state["whatsapp_message_id"])
    except Exception as e:
        logger.warning(f"Read receipt failed: {e}")

    try:
        await wa.send_typing_indicator(phone_id, state["whatsapp_message_id"])
    except Exception as e:
        logger.warning(f"Typing indicator failed: {e}")

    db = get_db()

    # Save inbound message
    await db.message_audit_log.insert_one({
        "message_id": str(uuid4()),
        "whatsapp_message_id": state["whatsapp_message_id"],
        "session_id": state["session_id"],
        "tenant_id": state["tenant_id"],
        "direction": "INBOUND",
        "sender": state["customer_phone"],
        "text_content": state["inbound_text"],
        "media_url": None,
        "media_type": state.get("inbound_media_type"),
        "agent_state": "TYPING",
        "is_read": True,
        "timestamp": datetime.utcnow(),
    })

    # Update session status
    await db.chat_sessions.update_one(
        {"session_id": state["session_id"]},
        {"$set": {"status": "AGENT_RESPONDING", "last_message_at": datetime.utcnow()}},
    )

    state["session_status"] = "AGENT_RESPONDING"
    return state


# ---------------------------------------------------------------------------
# Node 2: Context Retriever
# ---------------------------------------------------------------------------

async def context_retriever_node(state: AgentState) -> AgentState:
    """
    Fetches tenant config, last 5 messages, RAG chunks.
    Bonus B2: if user sent image, analyses with Gemini Vision.
    """
    db = get_db()

    # Tenant config
    tenant = await db.tenants.find_one({"tenant_id": state["tenant_id"]})
    if not tenant:
        state["error"] = f"Tenant {state['tenant_id']} not found"
        return state
    state["tenant_config"] = tenant

    # Catalog inventory (names) so the bot is HONEST about what actually exists
    cat = await db.catalog_items.find(
        {"tenant_id": state["tenant_id"], "is_active": True}, {"name": 1}
    ).to_list(None)
    state["catalog_names"] = [c["name"] for c in cat]

    # Last 5 messages (oldest first)
    msgs = await db.message_audit_log.find(
        {"session_id": state["session_id"]}
    ).sort("timestamp", -1).limit(5).to_list(5)
    state["chat_history"] = list(reversed(msgs))

    # RAG — make sure the in-memory index is built (Render free tier loses it on sleep/restart;
    # without this, the request that wakes the service would query an empty index).
    await ensure_index_ready()
    state["rag_chunks"] = search_knowledge_base(
        query=state["inbound_text"],
        tenant_id=state["tenant_id"],
    )

    # --- Visible flow logging ---
    logger.info(f"[INBOUND] ({tenant['name']}) customer said: {state['inbound_text']!r}")
    logger.info(f"[MONGODB] loaded {len(state['chat_history'])} prior messages from history")
    if state["rag_chunks"]:
        logger.info(f"[RAG/Chroma] found {len(state['rag_chunks'])} relevant knowledge chunks:")
        for i, c in enumerate(state["rag_chunks"], 1):
            logger.info(f"    [{i}] {c[:110]}...")
    else:
        logger.info("[RAG/Chroma] no relevant knowledge found -> LLM answers from system prompt only")

    # Inbound media: download once, then branch on PDF (document RAG) vs image (vision).
    if state.get("inbound_media_id"):
        try:
            tmp_url = await wa.get_media_url(state["inbound_media_id"])
            media_bytes = await wa.download_media(tmp_url)

            mime = (state.get("inbound_media_mime") or "").lower()
            fname = (state.get("inbound_media_filename") or "").lower()
            is_pdf = (
                media_bytes[:5] == b"%PDF-"
                or "pdf" in mime
                or fname.endswith(".pdf")
                or (state.get("inbound_media_type") == "document" and not mime.startswith("image/"))
            )

            if is_pdf:
                await _handle_inbound_pdf(state, db, media_bytes)
            else:
                await _handle_inbound_image(state, db, media_bytes)
        except Exception as e:
            logger.warning(f"Inbound media handling failed: {e}")

    return state


async def _handle_inbound_pdf(state: AgentState, db, pdf_bytes: bytes) -> None:
    """A customer sent a PDF. Persist it (dashboard view), chunk its text into the RAG
    knowledge base (so it's searchable on future turns), and stash the extracted text on
    the state so the bot can answer about it in THIS turn — no manual command, no restart."""
    from app.rag.pdf_extractor import ingest_text_pdf

    source_name = state.get("inbound_media_filename") or f"customer_{state['whatsapp_message_id']}.pdf"

    # Persist to GridFS so the dashboard shows the file the customer sent.
    try:
        stored_id = await gridfs.upload_bytes(
            data=pdf_bytes, filename=source_name, content_type="application/pdf",
            metadata={"tenant_id": state["tenant_id"], "direction": "INBOUND"},
        )
        stored_url = gridfs.public_url(stored_id, source_name)
        await db.message_audit_log.update_one(
            {"whatsapp_message_id": state["whatsapp_message_id"], "direction": "INBOUND"},
            {"$set": {"media_url": stored_url, "media_type": "DOCUMENT"}},
        )
        logger.info(f"[INBOUND PDF] stored to GridFS -> {stored_url}")
    except Exception as e:
        logger.warning(f"Failed to persist inbound PDF: {e}")

    # Chunk + embed into the tenant's knowledge base (this is the RAG ingestion that
    # previously only ran via the dashboard / manual commands).
    try:
        summary = await ingest_text_pdf(
            state["tenant_id"], pdf_bytes, source_name, rebuild=True
        )
        logger.info(
            f"[INBOUND PDF] ingested {summary.get('text_chunks', 0)} chunks "
            f"from {summary.get('pages', 0)} pages of {source_name!r}"
        )
        preview = summary.get("preview") or ""
        if preview:
            state["inbound_doc_summary"] = (
                f"The customer sent a PDF named '{source_name}'. Its text contents are:\n{preview}"
            )
        elif summary.get("note"):
            state["inbound_doc_summary"] = (
                f"The customer sent a PDF named '{source_name}', but {summary['note']}"
            )
    except Exception as e:
        logger.warning(f"Inbound PDF ingestion failed: {e}")


async def _handle_inbound_image(state: AgentState, db, img_bytes: bytes) -> None:
    """A customer sent an image. Persist it and describe it with Gemini Vision (bonus B2)."""
    # Persist the customer-sent image to GridFS so the dashboard can show it.
    # (Meta's media URL expires in ~5 min, so we must store it ourselves.)
    try:
        stored_id = await gridfs.upload_bytes(
            data=img_bytes,
            filename=f"inbound_{state['whatsapp_message_id']}.jpg",
            content_type="image/jpeg",
            metadata={"tenant_id": state["tenant_id"], "direction": "INBOUND"},
        )
        stored_url = gridfs.public_url(stored_id)
        await db.message_audit_log.update_one(
            {"whatsapp_message_id": state["whatsapp_message_id"], "direction": "INBOUND"},
            {"$set": {"media_url": stored_url, "media_type": "IMAGE"}},
        )
        logger.info(f"[INBOUND IMAGE] stored to GridFS -> {stored_url}")
    except Exception as e:
        logger.warning(f"Failed to persist inbound image: {e}")

    # Gemini Vision description (fed into the LLM context)
    gem = _get_gemini()
    if gem is None:
        logger.warning("Gemini client not available — skipping vision description")
        return
    vision_resp = gem.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            types.Part.from_text(text=(
                "Describe this image concisely for a customer service agent. "
                "Focus on: what product or item is shown, its appearance, condition, "
                "color, style, and any details relevant to helping the customer."
            )),
        ],
    )
    state["inbound_image_description"] = vision_resp.text
    logger.info(f"[VISION] {(state['inbound_image_description'] or '')[:100]}")


# ---------------------------------------------------------------------------
# Node 3: LLM Reasoning
# ---------------------------------------------------------------------------

def _build_system_prompt(tenant: dict, rag_chunks: list, catalog_names: list | None = None) -> str:
    prompt = tenant["system_prompt"]

    # Tell the LLM what's in the catalog so it's HONEST about what exists — but CAP the
    # list so a big catalog doesn't bloat the prompt (which blows Groq's per-minute limit).
    if catalog_names:
        shown = catalog_names[:20]
        prompt += "\n\n--- SAMPLE OF YOUR CATALOG ---\n"
        for n in shown:
            prompt += f"- {n}\n"
        if len(catalog_names) > len(shown):
            prompt += f"...and {len(catalog_names) - len(shown)} more products.\n"
        prompt += (
            "Use the search_catalog tool to find a specific product before describing or sending it. "
            "Never invent products you don't have; if you're unsure, search first or offer the full *catalog*.\n"
            "--- END CATALOG ---\n"
        )

    # Tell the LLM EXACTLY what media files exist so it never promises
    # or re-sends something it doesn't have.
    media_lib = tenant.get("media_library", {})
    if media_lib:
        # Deduplicate by URL (e.g. 'catalog' and 'brochure' may share one file)
        seen_urls = {}
        for keyword, url in media_lib.items():
            seen_urls.setdefault(url, []).append(keyword)
        prompt += "\n\n--- MEDIA YOU CAN SEND (via get_media tool) ---\n"
        for url, keywords in seen_urls.items():
            kind = "PDF document" if url.lower().endswith(".pdf") else "image"
            prompt += f"- {kind}: ask with keyword '{keywords[0]}'\n"
        prompt += (
            "This is the COMPLETE list of files you have. You have exactly ONE file per item above.\n"
            "If a customer asks for 'more' images or something not in this list, do NOT re-send the same "
            "file. Instead, honestly say that's the piece you have on hand and offer the full *catalog* "
            "to see the complete range. Only call get_media when the customer actually wants to receive a file.\n"
            "--- END MEDIA LIST ---\n"
        )

    if rag_chunks:
        prompt += "\n\n--- RELEVANT KNOWLEDGE BASE ---\n"
        for i, chunk in enumerate(rag_chunks[:4], 1):     # cap count
            prompt += f"\n[{i}] {chunk[:500]}\n"          # and length, to limit tokens
        prompt += "\n--- END KNOWLEDGE BASE ---\n"
        prompt += (
            "\nBase your answer on the knowledge base above. "
            "Do not fabricate prices, specs, or policies not mentioned."
        )
    return prompt


async def _media_kind(url: str) -> str:
    """
    Decide whether a media URL is a 'DOCUMENT' (PDF) or 'IMAGE'. Uses the file
    extension when present; for extension-less GridFS URLs (/files/<id>) it looks up
    the stored content_type — so PDFs uploaded via the dashboard are sent as documents,
    not as broken images.
    """
    low = (url or "").split("?")[0].lower()
    if low.endswith(".pdf"):
        return "DOCUMENT"
    if low.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return "IMAGE"
    if "/files/" in low:
        ref = url.split("?")[0].rstrip("/").split("/files/")[-1].split(".")[0]
        try:
            from bson import ObjectId
            doc = await get_db()["media.files"].find_one(
                {"_id": ObjectId(ref)}, {"metadata.content_type": 1, "filename": 1}
            )
            ct = ((doc or {}).get("metadata") or {}).get("content_type", "")
            fn = (doc or {}).get("filename", "")
            if "pdf" in ct.lower() or fn.lower().endswith(".pdf"):
                return "DOCUMENT"
        except Exception as e:
            logger.warning(f"_media_kind lookup failed for {url}: {e}")
    return "IMAGE"


async def llm_reasoning_node(state: AgentState) -> AgentState:
    """
    Primary reasoning via Groq (llama-3.3-70b) with tool calling.
    Tools: get_media, search_catalog, search_knowledge, escalate_to_human.
    """
    if state.get("error"):
        state["llm_reply"] = "Sorry, I'm having technical difficulties. Please try again shortly."
        return state

    tenant = state["tenant_config"]
    system_prompt = _build_system_prompt(tenant, state.get("rag_chunks") or [], state.get("catalog_names"))

    # Build OpenAI-style message list: system + last-5 history + current
    messages = [{"role": "system", "content": system_prompt}]
    for m in (state.get("chat_history") or [])[:-1]:
        role = "user" if m["direction"] == "INBOUND" else "assistant"
        if m.get("text_content"):
            messages.append({"role": role, "content": m["text_content"]})

    user_text = state["inbound_text"]
    if state.get("inbound_image_description"):
        user_text = f"[Customer sent an image: {state['inbound_image_description']}]\n{user_text}"
    if state.get("inbound_doc_summary"):
        user_text = f"[{state['inbound_doc_summary']}]\n{user_text}"
    messages.append({"role": "user", "content": user_text})

    groq = _get_groq()
    if not groq:
        state["llm_reply"] = "I'm here to help! Could you tell me a bit more about what you're looking for?"
        return state

    try:
        resp = await _groq_create(
            groq,
            model=settings.groq_model,
            messages=messages,
            tools=_groq_tools,
            tool_choice="auto",
            temperature=0.4,
            max_tokens=500,
        )
    except Exception as e:
        logger.error(f"Groq call failed after retries: {e}")
        # Don't blame the customer — be honest that we're momentarily busy.
        state["llm_reply"] = (
            "Sorry, I'm handling a lot of requests right now 🙏 Please give me a few "
            "seconds and ask again — I'll be right with you."
        )
        return state

    msg = resp.choices[0].message
    final_reply = msg.content
    media_url = media_type = media_filename = None

    if msg.tool_calls:
        # Files already sent earlier in this conversation (to avoid re-sending)
        already_sent = {
            m.get("media_url")
            for m in (state.get("chat_history") or [])
            if m.get("direction") == "OUTBOUND" and m.get("media_url")
        }

        # Record the assistant's tool-call turn, then a tool result per call
        messages.append({
            "role": "assistant", "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            result = {}

            if name == "get_media":
                keyword = (args.get("keyword") or "").lower()
                logger.info(f"[TOOL] get_media({keyword!r}) -> MongoDB media_library")
                matched = None
                for key, url in (tenant.get("media_library") or {}).items():
                    if keyword in key.lower() or key.lower() in keyword:
                        media_url, matched = url, key
                        media_type = await _media_kind(url)
                        if media_type == "DOCUMENT":
                            media_filename = f"{key.title().replace(' ', '_')}.pdf"
                        logger.info(f"[MEDIA] matched {key!r} -> {media_type}: {url}")
                        break
                result = ({"status": "sent", "item": matched, "type": media_type}
                          if matched else {"status": "not_found", "note": "No such file; offer the catalog instead."})

            elif name == "search_catalog":
                desc = args.get("description") or ""
                logger.info(f"[TOOL] search_catalog({desc!r}) -> Chroma catalog (image+data)")
                item = search_catalog(desc, state["tenant_id"])
                if item and item.get("image_url"):
                    if item["image_url"] in already_sent:
                        # Already shown this exact piece — acknowledge, don't resend, offer catalog
                        logger.info(f"[CATALOG] {item['name']!r} already shown -> acknowledge + offer catalog")
                        result = {
                            "found": True, "already_shown": True, "name": item["name"],
                            "note": (f"You ALREADY showed the {item['name']} earlier in this chat. Do NOT resend the image. "
                                     f"Tell the customer that, as you showed them, the {item['name']} is the piece you have "
                                     "in that style, then warmly offer the full *catalog* to explore the complete range."),
                        }
                    else:
                        media_url = item["image_url"]
                        media_type = await _media_kind(media_url)
                        if media_type == "DOCUMENT":
                            media_filename = f"{item['name'].replace(' ', '_')}.pdf"
                        logger.info(f"[CATALOG] matched {item['name']!r} -> {media_url}")
                        result = {"found": True, "name": item["name"], "price": item["price"], "details": item["details"]}
                else:
                    logger.info("[CATALOG] no match")
                    result = {"found": False, "note": "No matching product; offer the full catalog or ask for detail."}

            elif name == "search_knowledge":
                q = args.get("query") or ""
                extra = search_knowledge_base(q, state["tenant_id"])
                existing = state.get("rag_chunks") or []
                state["rag_chunks"] = existing + [c for c in extra if c not in existing]
                result = {"results": extra[:3] if extra else "no additional info found"}

            elif name == "escalate_to_human":
                logger.info("[TOOL] escalate_to_human -> NEEDS_HUMAN")
                state["session_status"] = "NEEDS_HUMAN"
                result = {"status": "escalated"}

            messages.append({
                "role": "tool", "tool_call_id": tc.id, "name": name,
                "content": json.dumps(result),
            })

        # Second call: let the model write the natural reply using tool results
        try:
            resp2 = await _groq_create(
                groq, model=settings.groq_model, messages=messages, temperature=0.5, max_tokens=400,
            )
            final_reply = resp2.choices[0].message.content or final_reply
        except Exception as e:
            logger.warning(f"Groq follow-up failed: {e}")

    # Fallbacks
    if not final_reply:
        if media_type == "DOCUMENT":
            final_reply = "Here you go! 📄 Let me know if anything catches your eye."
        elif media_type == "IMAGE":
            final_reply = "Here it is! 😊 Want to see more? I can share our full catalog."
        else:
            final_reply = "I'm here to help! Could you tell me a bit more about what you're looking for?"

    # HONESTY GUARD: never claim to have sent/attached a file when none is attached
    # (stops "I've sent you the s5 image" when search found nothing).
    if not media_url and re.search(
        r"(i'?ve sent|i have sent|just sent|sent you|i'?ve attached|attached is|"
        r"here'?s the (image|photo|picture|pdf|catalog|document|diagram|invoice|file))",
        final_reply or "", re.I,
    ):
        final_reply = (
            "Hmm, I don't have that exact file on hand 😊 — but I can share our full "
            "*catalog* so you can browse everything. Would you like me to send it over?"
        )

    state["llm_reply"] = final_reply
    # DEDUP: never re-send a file already sent recently in this conversation
    # (stops "Hello" re-sending the catalog and "any more?" re-sending the same sofa).
    if media_url:
        recent_media = {
            m.get("media_url")
            for m in (state.get("chat_history") or [])
            if m.get("direction") == "OUTBOUND" and m.get("media_url")
        }
        if media_url in recent_media:
            logger.info(f"[DEDUP] {media_url} already sent recently -> text only")
            media_url = media_type = media_filename = None

    state["media_to_send"] = media_url
    state["media_type"] = media_type
    state["media_filename"] = media_filename

    logger.info(f"[REPLY] {final_reply[:150]!r}")
    if media_url:
        logger.info(f"[REPLY] + attaching {media_type}: {media_filename or media_url}")
    logger.info(f"[STATUS] session -> {state['session_status']}")
    return state


# ---------------------------------------------------------------------------
# Node 4: Dispatcher
# ---------------------------------------------------------------------------

async def dispatcher_node(state: AgentState) -> AgentState:
    """
    Sends WhatsApp reply (text + optional media).
    Saves outbound message to MongoDB.
    Updates session status.
    Typing indicator auto-stops when a message is sent.
    """
    phone_id = state["tenant_config"]["whatsapp_phone_number_id"]
    to = state["customer_phone"]
    db = get_db()

    try:
        await wa.send_text_message(phone_id, to, state["llm_reply"])
    except Exception as e:
        logger.error(f"Failed to send text message: {e}")

    if state.get("media_to_send"):
        try:
            if state["media_type"] == "IMAGE":
                await wa.send_image_message(phone_id, to, state["media_to_send"])
            elif state["media_type"] == "DOCUMENT":
                await wa.send_document_message(
                    phone_id, to, state["media_to_send"], state["media_filename"]
                )
        except Exception as e:
            logger.error(f"Failed to send media: {e}")

    # Determine final status. After a normal reply the bot stays ON DUTY
    # (WAITING_FOR_BOT) — it is NOT "resolved". RESOLVED is a human action only.
    # If the turn escalated, keep NEEDS_HUMAN so auto-replies stay paused.
    new_status = "NEEDS_HUMAN" if state["session_status"] == "NEEDS_HUMAN" else "WAITING_FOR_BOT"

    # Save outbound message
    await db.message_audit_log.insert_one({
        "message_id": str(uuid4()),
        "session_id": state["session_id"],
        "tenant_id": state["tenant_id"],
        "direction": "OUTBOUND",
        "sender": "BOT",
        "text_content": state["llm_reply"],
        "media_url": state.get("media_to_send"),
        "media_type": state.get("media_type"),
        "media_filename": state.get("media_filename"),
        "agent_state": "SENT",
        "timestamp": datetime.utcnow(),
    })

    # Update session
    await db.chat_sessions.update_one(
        {"session_id": state["session_id"]},
        {
            "$set": {"status": new_status, "last_message_at": datetime.utcnow()},
            "$inc": {"message_count": 2},
        },
    )

    state["session_status"] = new_status
    return state
