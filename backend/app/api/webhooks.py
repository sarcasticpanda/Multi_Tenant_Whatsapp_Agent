import json
import logging
import re
from collections import Counter
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import PlainTextResponse, Response
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.agent.graph import agent_graph
from app.agent.state import AgentState
from app.config import settings
from app.db.mongodb import get_db
from app.whatsapp.client import verify_webhook_signature, send_text_message

router = APIRouter()
logger = logging.getLogger(__name__)


def _extract_message(payload: dict) -> dict | None:
    """Parses Meta webhook payload. Returns None for status updates."""
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        if "statuses" in value or "messages" not in value:
            return None

        message = value["messages"][0]
        metadata = value["metadata"]
        msg_type = message["type"]

        text = ""
        media_id = None
        media_type = None
        media_filename = None
        media_mime = None

        if msg_type == "text":
            text = message["text"]["body"]
        elif msg_type == "image":
            media_id = message["image"]["id"]
            text = message["image"].get("caption", "")
            media_type = "image"
            media_mime = message["image"].get("mime_type")
        elif msg_type == "document":
            media_id = message["document"]["id"]
            text = message["document"].get("caption", "")
            media_type = "document"
            media_filename = message["document"].get("filename")
            media_mime = message["document"].get("mime_type")
        else:
            # Unsupported type (audio, video, etc.) — skip
            return None

        return {
            "phone_number_id": metadata["phone_number_id"],
            "customer_phone": message["from"],
            "message_id": message["id"],
            "text": text,
            "media_id": media_id,
            "media_type": media_type,
            "media_filename": media_filename,
            "media_mime": media_mime,
            "timestamp": message.get("timestamp"),
        }
    except (KeyError, IndexError):
        return None


# Generic retail words that don't identify a specific brand.
_STOPWORDS = {
    "store", "stores", "services", "service", "care", "company", "shop", "the", "and",
    "for", "ltd", "inc", "llp", "pvt", "limited", "private", "solutions", "group",
    "world", "house", "hub", "center", "centre", "online", "official",
}


def _signals_from(*phrases) -> set[str]:
    """Turn keywords/names into routing signals: the full phrase plus its individual
    words (>=3 chars, minus generic stopwords). 'oil change' -> {'oil change','oil','change'}."""
    out: set[str] = set()
    for p in phrases:
        p = (p or "").lower().strip()
        if len(p) >= 3:
            out.add(p)  # keep the full phrase too, so 'oil change' can match as a unit
        for w in re.split(r"[\s/_\-]+", p):
            if len(w) >= 3 and w not in _STOPWORDS:
                out.add(w)
    return {s for s in out if s not in _STOPWORDS}


async def _tenant_vocab(db, tenant: dict) -> set[str]:
    """Everything that could point at this tenant: media keywords, switch code,
    brand name words, and its catalog product names."""
    sig = _signals_from(*(tenant.get("media_library") or {}).keys())
    sig |= _signals_from(tenant.get("switch_code"), tenant["name"])
    items = await db.catalog_items.find(
        {"tenant_id": tenant["tenant_id"]}, {"_id": 0, "name": 1}
    ).to_list(None)
    sig |= _signals_from(*[it.get("name") for it in items])
    return sig


def _best_tenant(text: str, vocab_by_tenant: dict[str, set[str]]) -> str | None:
    """
    Confident auto-route. Only 'discriminating' signals count — ones owned by exactly ONE
    tenant. A word shared by two tenants (e.g. 'price') is ignored, since it tells us nothing.
    The tenant whose discriminating words appear most in the message wins; a tie -> None (ask).
    """
    t = (text or "").lower()
    if not t.strip():
        return None
    counts = Counter(s for vocab in vocab_by_tenant.values() for s in vocab)
    scores: dict[str, int] = {}
    for tid, vocab in vocab_by_tenant.items():
        score = sum(
            1 for s in vocab
            if counts[s] == 1 and re.search(rf"\b{re.escape(s)}\b", t)
        )
        if score:
            scores[tid] = score
    if not scores:
        return None
    top = max(scores.values())
    leaders = [tid for tid, sc in scores.items() if sc == top]
    return leaders[0] if len(leaders) == 1 else None


async def _resolve_or_triage(db, customer_phone: str, phone_number_id: str, text: str):
    """
    Decide which tenant a customer belongs to. Returns (tenant_id, ask_reply).
    Exactly one of the two is set:
      - tenant_id set  -> route the message to that tenant
      - ask_reply set  -> we couldn't tell; send this 'which business?' menu instead

    Priority:
      1. Explicit routing assignment (customer_routing)            -> tenant_id
      2. Existing session (sticky to their current tenant)         -> tenant_id
      3. A number that uniquely belongs to one tenant (production) -> tenant_id
      4. Shared number + only one tenant exists                    -> tenant_id
      5. Shared number, unassigned: auto-guess from media words    -> tenant_id (confident)
         ...otherwise ask which business                          -> ask_reply
    """
    route = await db.customer_routing.find_one({"customer_phone": customer_phone})
    if route:
        return route["tenant_id"], None

    existing = await db.chat_sessions.find_one(
        {"customer_phone": customer_phone}, sort=[("last_message_at", -1)]
    )
    if existing:
        return existing["tenant_id"], None

    owners = await db.tenants.find(
        {"whatsapp_phone_number_id": phone_number_id, "is_active": True}
    ).to_list(None)
    if len(owners) == 1:  # this number is dedicated to one tenant -> deterministic
        return owners[0]["tenant_id"], None

    # Shared (or unowned) number: triage among the candidate tenants.
    candidates = owners or await db.tenants.find({"is_active": True}).to_list(None)
    if not candidates:
        return None, None
    if len(candidates) == 1:
        return candidates[0]["tenant_id"], None

    vocab_by_tenant = {c["tenant_id"]: await _tenant_vocab(db, c) for c in candidates}
    guess = _best_tenant(text, vocab_by_tenant)
    if guess:
        logger.info(f"[TRIAGE] auto-routed unassigned customer to {guess} from message keywords")
        return guess, None

    # Not confident -> ask the customer which business they want.
    # Enumerate only when the list is short; at scale (many tenants on one number),
    # just ask for the name instead of printing an unusable list.
    nudge = "or just tell me what you need (e.g. a *sofa* or an *oil change*)"
    if len(candidates) <= 6:
        options = "\n".join(f"• {c['name']}" for c in candidates)
        reply = (
            "Hi! 👋 Thanks for reaching out. Which business would you like to chat with today?\n\n"
            f"{options}\n\nReply with the name, {nudge}."
        )
    else:
        reply = (
            "Hi! 👋 Thanks for reaching out. Please reply with the *name* of the business "
            f"you'd like to reach, {nudge}, and I'll connect you."
        )
    return None, reply


async def _handle_switch_command(db, text: str, customer_phone: str, phone_number_id: str) -> bool:
    """
    Lets a customer change which tenant they're talking to with an explicit command.
    Proper, scalable format (no list of 50 tenants needed):
      - '#autocare'                -> switch by code
      - 'switch to AutoCare'       -> switch by name
      - 'switch'                   -> show a short picker (capped) + how to choose
    In production each tenant has its own number, so this is a shared-number helper.

    Returns True if the message was a switch command (handled here, skip the agent).
    """
    from app.whatsapp.client import send_text_message

    stripped = (text or "").strip()
    low = stripped.lower()

    # Detect intent + extract the target. Only '#...' or a message starting with
    # 'switch' counts — so normal sentences ('change my oil') never trigger.
    if stripped.startswith("#"):
        target = stripped[1:].strip().lower()
    elif re.match(r"^switch\b", low):
        target = re.sub(r"^switch(\s+to)?(\s+(?:a\s+)?(?:business|tenant|brand))?", "", low).strip()
    else:
        return False

    tenants = await db.tenants.find({"is_active": True}).to_list(None)

    def _code_of(t):
        return (t.get("switch_code") or t["tenant_id"]).lower()

    # No target -> show a capped picker with the exact format to use.
    if not target or target in ("help", "tenants", "business", "list"):
        shown = tenants[:6]
        opts = "\n".join(f"• {t['name']} — reply *#{_code_of(t)}*" for t in shown)
        more = "" if len(tenants) <= 6 else f"\n…and {len(tenants) - 6} more."
        await send_text_message(phone_number_id, customer_phone,
            f"Which business would you like to chat with?\n{opts}{more}\n\nReply with its *#code*, or type *switch to <name>*.")
        return True

    def _matches(t):
        name = t["name"].lower()
        words = set(re.split(r"[\s/_\-]+", name))
        return (_code_of(t) == target or t["tenant_id"].lower() == target
                or target in name or target in words)

    matches = [t for t in tenants if _matches(t)]
    if len(matches) != 1:
        hint = "I couldn't tell which business you meant" if len(matches) > 1 else f"I don't recognise “{target}”"
        await send_text_message(phone_number_id, customer_phone,
            f"{hint}. Type *switch* to see the options.")
        return True
    match = matches[0]

    await db.customer_routing.update_one(
        {"customer_phone": customer_phone},
        {"$set": {"customer_phone": customer_phone, "tenant_id": match["tenant_id"]}},
        upsert=True,
    )
    # Make sure a session exists so the conversation appears in that tenant's dashboard
    await _get_or_create_session(match["tenant_id"], customer_phone)
    await send_text_message(phone_number_id, customer_phone,
        f"You're now chatting with *{match['name']}*. How can we help? 😊")
    return True


async def _get_or_create_session(tenant_id: str, customer_phone: str) -> dict:
    """Atomic get-or-create. Avoids a find-then-insert race on concurrent inbound messages."""
    db = get_db()
    now = datetime.utcnow()
    session = await db.chat_sessions.find_one_and_update(
        {"tenant_id": tenant_id, "customer_phone": customer_phone},
        {
            "$setOnInsert": {
                "session_id": str(uuid4()),
                "tenant_id": tenant_id,
                "customer_phone": customer_phone,
                "status": "WAITING_FOR_BOT",
                "context_vars": {},
                "message_count": 0,
                "created_at": now,
            },
            "$set": {"last_message_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return session


async def _run_agent(message_data: dict, tenant_id: str, session_id: str):
    """Background task: runs LangGraph pipeline."""
    try:
        # Fetch tenant config first (needed in Acknowledge node)
        db = get_db()
        tenant = await db.tenants.find_one({"tenant_id": tenant_id})

        initial_state: AgentState = {
            "tenant_id": tenant_id,
            "customer_phone": message_data["customer_phone"],
            "session_id": session_id,
            "whatsapp_message_id": message_data["message_id"],
            "inbound_text": message_data["text"] or "(no text)",
            "inbound_media_id": message_data.get("media_id"),
            "inbound_media_type": message_data.get("media_type"),
            "inbound_media_filename": message_data.get("media_filename"),
            "inbound_media_mime": message_data.get("media_mime"),
            "inbound_image_description": None,
            "inbound_doc_summary": None,
            "tenant_config": tenant,
            "chat_history": None,
            "rag_chunks": None,
            "llm_reply": None,
            "media_to_send": None,
            "media_type": None,
            "media_filename": None,
            "session_status": "AGENT_RESPONDING",
            "error": None,
        }

        await agent_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Agent pipeline error: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# GET — Meta webhook verification
# ---------------------------------------------------------------------------

@router.get("/api/webhooks/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        return PlainTextResponse(content=hub_challenge)
    return Response(status_code=403)


# ---------------------------------------------------------------------------
# POST — Receive inbound messages
# ---------------------------------------------------------------------------

@router.post("/api/webhooks/whatsapp")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    # Bonus B1: signature validation FIRST.
    # Enforce when META_APP_SECRET is configured — reject if header missing or invalid.
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if settings.meta_app_secret:
        if not verify_webhook_signature(payload_bytes, signature):
            logger.warning("Invalid/missing webhook signature — rejected")
            return Response(status_code=403)

    payload = json.loads(payload_bytes) if payload_bytes else {}

    message_data = _extract_message(payload)
    if not message_data:
        # Status update or unsupported type — acknowledge and ignore
        return Response(status_code=200)

    db = get_db()

    # IDEMPOTENCY: Meta retries webhooks. Process each message_id exactly once.
    # Atomic unique insert; on duplicate, this is a retry — skip silently.
    try:
        await db.processed_webhooks.insert_one({
            "whatsapp_message_id": message_data["message_id"],
            "received_at": datetime.utcnow(),
        })
    except DuplicateKeyError:
        logger.info(f"Duplicate webhook for {message_data['message_id']} — already processed, skipping")
        return Response(status_code=200)

    # Optional one-phone helper: '#code' switches which tenant this customer talks to.
    if await _handle_switch_command(
        db, message_data["text"], message_data["customer_phone"], message_data["phone_number_id"]
    ):
        return Response(status_code=200)

    # Resolve which TENANT this customer belongs to (or ask them, if we can't tell).
    tenant_id, ask_reply = await _resolve_or_triage(
        db, message_data["customer_phone"], message_data["phone_number_id"], message_data["text"]
    )
    if ask_reply:
        # Unassigned customer on a shared number, message not confident enough to route.
        await send_text_message(message_data["phone_number_id"], message_data["customer_phone"], ask_reply)
        return Response(status_code=200)
    if not tenant_id:
        logger.warning("No tenant could be resolved — ignoring")
        return Response(status_code=200)

    # Get or create session
    session = await _get_or_create_session(tenant_id, message_data["customer_phone"])

    # If session needs human — log message but don't run agent
    if session["status"] == "NEEDS_HUMAN":
        logger.info(f"Session {session['session_id']} needs human — skipping agent")
        return Response(status_code=200)

    # RETURN 200 IMMEDIATELY — LangGraph runs in background
    background_tasks.add_task(
        _run_agent, message_data, tenant_id, session["session_id"]
    )
    return Response(status_code=200)
