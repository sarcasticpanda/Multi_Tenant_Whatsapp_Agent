from app.db.mongodb import get_db
from app.db.models import TenantModel
from app.config import settings
from datetime import datetime


TENANT_A = {
    "tenant_id": "tenant_a",
    "name": "Luxury Furniture Store",
    "system_prompt": (
        "You are Aria, a personal design concierge for Lumière, a luxury furniture house. "
        "You speak like a warm, confident human expert — never robotic, never repetitive. "
        "Keep replies short and natural for WhatsApp (2-4 sentences max). Use *bold* for product names "
        "and _italics_ for prices. A tasteful emoji occasionally is fine, never more than one.\n\n"
        "Your goals: help customers find the perfect piece, answer with REAL facts from your knowledge base, "
        "and gently move them toward visiting a showroom or requesting the catalog.\n\n"
        "Rules:\n"
        "- When a customer wants to SEE something (catalog, price list, a sofa, the showroom), call get_media.\n"
        "- Answer product/price/delivery/warranty questions ONLY from your knowledge base. If you don't know, "
        "say so honestly and offer to connect them with a design consultant.\n"
        "- Never invent prices, dimensions, or policies.\n"
        "- Don't repeat the same greeting every message — you remember the conversation.\n"
        "- Be genuinely helpful and a little charming, like a high-end store associate."
    ),
    "whatsapp_phone_number_id": settings.meta_phone_number_id,
    "media_library": {
        "catalog": f"{settings.app_base_url}/static/furniture_catalog.pdf",
        "brochure": f"{settings.app_base_url}/static/furniture_catalog.pdf",
        "sofa": f"{settings.app_base_url}/static/sofa.jpg",
        "showroom": f"{settings.app_base_url}/static/showroom.png",
        "price list": f"{settings.app_base_url}/static/price_list.pdf",
        "pricing": f"{settings.app_base_url}/static/price_list.pdf",
    },
    "is_active": True,
    "created_at": datetime.utcnow(),
}

TENANT_B = {
    "tenant_id": "tenant_b",
    "name": "AutoCare Services",
    "system_prompt": (
        "You are Max, the service advisor at AutoCare, a trusted car service center. "
        "You talk like a friendly, no-nonsense mechanic who genuinely wants to help — clear, quick, and honest. "
        "Keep replies short for WhatsApp (2-4 sentences). Use *bold* for service names and _italics_ for prices. "
        "One emoji at most.\n\n"
        "Your goals: help customers understand what their car needs, give accurate pricing from your knowledge base, "
        "and get them to book an appointment.\n\n"
        "Rules:\n"
        "- When a customer wants the invoice, service menu, or a repair diagram, call get_media.\n"
        "- Quote prices, service times, and packages ONLY from your knowledge base. If unsure, say so and offer to "
        "have a technician call them.\n"
        "- Never make up prices or guarantee fixes you can't confirm.\n"
        "- Don't re-introduce yourself every message — keep the conversation flowing naturally.\n"
        "- Be practical and reassuring, like a mechanic customers actually trust."
    ),
    "whatsapp_phone_number_id": settings.meta_phone_number_id,
    "media_library": {
        "invoice": f"{settings.app_base_url}/static/invoice_template.pdf",
        "repair diagram": f"{settings.app_base_url}/static/repair_diagram.jpg",
        "diagram": f"{settings.app_base_url}/static/repair_diagram.jpg",
        "service menu": f"{settings.app_base_url}/static/invoice_template.pdf",
        "price": f"{settings.app_base_url}/static/invoice_template.pdf",
    },
    "is_active": True,
    "created_at": datetime.utcnow(),
}


async def ensure_indexes() -> None:
    """
    Create all indexes. Runs on EVERY startup (idempotent) — not just first seed,
    so an existing/production DB always has its constraints.
    """
    db = get_db()
    await db.tenants.create_index("tenant_id", unique=True)
    await db.tenants.create_index("whatsapp_phone_number_id")

    await db.chat_sessions.create_index(
        [("tenant_id", 1), ("customer_phone", 1)], unique=True
    )
    await db.chat_sessions.create_index("tenant_id")
    await db.chat_sessions.create_index("status")
    await db.chat_sessions.create_index([("last_message_at", -1)])

    await db.message_audit_log.create_index([("session_id", 1), ("timestamp", 1)])
    await db.message_audit_log.create_index("tenant_id")
    await db.message_audit_log.create_index([("timestamp", -1)])

    await db.knowledge_docs.create_index("tenant_id")
    await db.knowledge_docs.create_index("doc_type")

    # Idempotency: unique index so a given inbound WhatsApp message is processed once.
    await db.processed_webhooks.create_index("whatsapp_message_id", unique=True)
    print("Ensured all MongoDB indexes")


async def seed_tenants_if_empty() -> None:
    db = get_db()
    await ensure_indexes()
    count = await db.tenants.count_documents({})
    if count == 0:
        await db.tenants.insert_many([TENANT_A, TENANT_B])
        print("Seeded Tenant A (Luxury Furniture) and Tenant B (AutoCare)")
    else:
        print(f"Tenants already seeded ({count} found)")
