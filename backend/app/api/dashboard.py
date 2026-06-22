from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db.mongodb import get_db
from app.whatsapp.client import send_text_message
from app.config import settings

router = APIRouter()


@router.get("/api/tenants")
async def list_tenants():
    db = get_db()
    tenants = await db.tenants.find(
        {}, {"_id": 0, "tenant_id": 1, "name": 1, "is_active": 1}
    ).to_list(None)
    return {"tenants": tenants}


@router.get("/api/tenants/{tenant_id}/sessions")
async def list_sessions(tenant_id: str):
    db = get_db()
    sessions = await db.chat_sessions.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("last_message_at", -1).to_list(None)

    # Convert datetime to ISO string for JSON
    for s in sessions:
        for field in ("last_message_at", "created_at"):
            if s.get(field):
                s[field] = s[field].isoformat()

    return {"sessions": sessions}


@router.get("/api/sessions/{session_id}/messages")
async def list_messages(session_id: str):
    db = get_db()
    messages = await db.message_audit_log.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("timestamp", 1).to_list(None)

    for m in messages:
        if m.get("timestamp"):
            m["timestamp"] = m["timestamp"].isoformat()

    return {"messages": messages}


@router.get("/api/tenants/{tenant_id}/stats")
async def tenant_stats(tenant_id: str):
    db = get_db()
    total = await db.chat_sessions.count_documents({"tenant_id": tenant_id})
    resolved = await db.chat_sessions.count_documents({"tenant_id": tenant_id, "status": "RESOLVED"})
    needs_human = await db.chat_sessions.count_documents({"tenant_id": tenant_id, "status": "NEEDS_HUMAN"})
    active = await db.chat_sessions.count_documents({"tenant_id": tenant_id, "status": "AGENT_RESPONDING"})
    return {
        "total_sessions": total,
        "resolved": resolved,
        "needs_human": needs_human,
        "active": active,
    }


class BroadcastRequest(BaseModel):
    tenant_id: str
    phone_numbers: list[str]
    message: str


@router.post("/api/broadcast")
async def broadcast(req: BroadcastRequest):
    db = get_db()
    tenant = await db.tenants.find_one({"tenant_id": req.tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    results = {"sent": [], "failed": []}
    for phone in req.phone_numbers:
        try:
            await send_text_message(
                tenant["whatsapp_phone_number_id"], phone, req.message
            )
            results["sent"].append(phone)
        except Exception as e:
            results["failed"].append({"phone": phone, "error": str(e)})

    return results
