import json
import logging
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
from app.whatsapp.client import verify_webhook_signature

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

        if msg_type == "text":
            text = message["text"]["body"]
        elif msg_type == "image":
            media_id = message["image"]["id"]
            text = message["image"].get("caption", "")
            media_type = "image"
        elif msg_type == "document":
            media_id = message["document"]["id"]
            text = message["document"].get("caption", "")
            media_type = "document"
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
            "timestamp": message.get("timestamp"),
        }
    except (KeyError, IndexError):
        return None


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
            "inbound_image_description": None,
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

    # Find tenant by phone_number_id
    tenant = await db.tenants.find_one(
        {"whatsapp_phone_number_id": message_data["phone_number_id"]}
    )
    if not tenant:
        logger.warning(f"No tenant for phone_number_id {message_data['phone_number_id']}")
        return Response(status_code=200)

    tenant_id = tenant["tenant_id"]

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
