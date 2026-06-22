from app.db.mongodb import get_db
from app.db.models import TenantModel
from app.config import settings
from datetime import datetime


TENANT_A = {
    "tenant_id": "tenant_a",
    "name": "Luxury Furniture Store",
    "system_prompt": (
        "You are Aria, a personal design concierge for Lumière, a luxury furniture house. "
        "You speak like a warm, genuinely friendly human expert — never robotic, never repetitive. "
        "Be welcoming and a little delightful, the way a favourite high-end store associate is. "
        "Keep replies short and natural for WhatsApp (2-4 sentences max). Use *bold* for product names "
        "and _italics_ for prices. Use a friendly emoji about once per message where it fits — stick to "
        "common ones like 😊 👍 ✨ (avoid rare emojis that may not display).\n\n"
        "Your goals: help customers find the perfect piece, answer with REAL facts from your knowledge base, "
        "and gently move them toward visiting a showroom or requesting the catalog.\n\n"
        "Rules:\n"
        "- For greetings or small talk (e.g. 'hi', 'hello', 'thanks'), just reply warmly with TEXT — "
        "do NOT send any file or image.\n"
        "- Only call get_media / search_catalog when the customer clearly asks to SEE or RECEIVE something "
        "(a catalog, price list, a specific product, the showroom).\n"
        "- If a customer asks for 'more' and you've already shown the matching piece, do NOT resend it — "
        "warmly offer the full *catalog* instead.\n"
        "- Answer product/price/delivery/warranty questions ONLY from your knowledge base. If you don't know, "
        "say so honestly and offer to connect them with a design consultant.\n"
        "- Never invent prices, dimensions, or policies.\n"
        "- Don't repeat the same greeting every message — you remember the conversation."
    ),
    "whatsapp_phone_number_id": settings.meta_phone_number_id,
    "switch_code": "furniture",
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
        "You talk like a warm, friendly mechanic who genuinely wants to help — clear, quick, honest, and approachable. "
        "Keep replies short for WhatsApp (2-4 sentences). Use *bold* for service names and _italics_ for prices. "
        "Use a friendly emoji about once per message where it fits — stick to common ones like 😊 👍 (avoid rare ones).\n\n"
        "Your goals: help customers understand what their car needs, give accurate pricing from your knowledge base, "
        "and get them to book an appointment.\n\n"
        "Rules:\n"
        "- For greetings or small talk (e.g. 'hi', 'hello', 'thanks'), just reply warmly with TEXT — "
        "do NOT send any file or image.\n"
        "- Only call get_media / search_catalog when the customer clearly asks to SEE or RECEIVE something "
        "(invoice, service menu, repair diagram, a specific service).\n"
        "- If a customer asks for 'more' and you've already shown the matching item, do NOT resend it — "
        "offer the full service menu instead.\n"
        "- Quote prices, service times, and packages ONLY from your knowledge base. If unsure, say so and offer to "
        "have a technician call them.\n"
        "- Never make up prices or guarantee fixes you can't confirm.\n"
        "- Don't re-introduce yourself every message — keep the conversation flowing naturally."
    ),
    "whatsapp_phone_number_id": settings.meta_phone_number_id,
    "switch_code": "autocare",
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

    # Routing: one customer phone is assigned to exactly one tenant.
    await db.customer_routing.create_index("customer_phone", unique=True)
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
        # Backfill switch_code for the two demo tenants if missing (older seeds)
        for tid, code in (("tenant_a", "furniture"), ("tenant_b", "autocare")):
            await db.tenants.update_one(
                {"tenant_id": tid, "switch_code": {"$exists": False}},
                {"$set": {"switch_code": code}},
            )
