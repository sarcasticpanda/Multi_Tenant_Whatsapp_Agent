"""
Seeds the catalog_items collection: visual products with image + structured data linked.
The ai_description is what RAG searches; the image_url + price + attributes are returned together.
"""
from app.db.mongodb import get_db
from app.config import settings
from datetime import datetime
from uuid import uuid4


def _u(path: str) -> str:
    return f"{settings.app_base_url}/static/{path}"


CATALOG = [
    # ---- Tenant A: Luxury Furniture ----
    {
        "item_id": str(uuid4()), "tenant_id": "tenant_a", "name": "Milano Sofa",
        "image_url": _u("sofa.jpg"),
        "ai_description": "Premium Italian leather 3-seater sofa with a solid walnut frame and adjustable headrests. Elegant, modern silhouette available in deep emerald, cognac, ivory and more.",
        "price": "Rs 1,85,000",
        "attributes": {"colors": "8 (Ivory, Cognac, Emerald, Midnight Black, Navy, Blush, Charcoal, Cream)",
                       "material": "Italian leather", "frame": "solid walnut", "delivery_days": "28-42",
                       "dimensions": "220 x 90 x 85 cm"},
        "is_active": True, "created_at": datetime.utcnow(),
    },
    {
        "item_id": str(uuid4()), "tenant_id": "tenant_a", "name": "Valencia Dining Set",
        "image_url": _u("dining_set.jpg"),
        "ai_description": "Eight-seater dining set with a Carrara marble top and solid teak base, paired with Italian leather upholstered chairs. Grand, contemporary centerpiece for a formal dining room.",
        "price": "Rs 3,20,000",
        "attributes": {"seats": "8", "top": "Carrara marble", "base": "solid teak",
                       "material": "Italian leather chairs", "delivery_days": "42-56",
                       "dimensions": "240 x 110 cm table"},
        "is_active": True, "created_at": datetime.utcnow(),
    },
    {
        "item_id": str(uuid4()), "tenant_id": "tenant_a", "name": "Monaco King Bed",
        "image_url": _u("bed_frame.jpg"),
        "ai_description": "Upholstered king-size bed frame with a padded button-tufted headboard in plush velvet. Available in grey velvet, ivory leather and emerald velvet. Luxurious and calm.",
        "price": "Rs 2,10,000",
        "attributes": {"size": "King (180 x 200 cm)", "headboard": "button-tufted padded",
                       "options": "Grey velvet, Ivory leather, Emerald velvet", "delivery_days": "35-49"},
        "is_active": True, "created_at": datetime.utcnow(),
    },
    {
        "item_id": str(uuid4()), "tenant_id": "tenant_a", "name": "Riviera Coffee Table",
        "image_url": _u("coffee_table.jpg"),
        "ai_description": "Minimalist coffee table with a tempered glass top and brushed steel frame. Clean lines, light and airy — pairs well with both modern and transitional living rooms.",
        "price": "Rs 65,000",
        "attributes": {"top": "tempered glass", "frame": "brushed steel",
                       "options": "Clear/silver, Smoked/gold", "delivery_days": "21-28",
                       "dimensions": "120 x 60 x 45 cm"},
        "is_active": True, "created_at": datetime.utcnow(),
    },
    # ---- Tenant B: Automotive Care ----
    {
        "item_id": str(uuid4()), "tenant_id": "tenant_b", "name": "Full AC Service",
        "image_url": _u("car_service.jpg"),
        "ai_description": "Complete car air-conditioning service: cleaning, R134a gas recharge, leak check and cabin filter replacement. Restores cold, fresh airflow for hot weather driving.",
        "price": "Rs 3,500",
        "attributes": {"includes": "cleaning, gas recharge, leak check, cabin filter",
                       "duration": "1-2 hours", "warranty": "3 months on gas"},
        "is_active": True, "created_at": datetime.utcnow(),
    },
    {
        "item_id": str(uuid4()), "tenant_id": "tenant_b", "name": "Brake Overhaul",
        "image_url": _u("brake_service.jpg"),
        "ai_description": "Full brake overhaul across all four wheels: brake pads, rotors and fluid replacement. Restores safe, responsive braking with a 6-month parts warranty.",
        "price": "Rs 14,000",
        "attributes": {"covers": "4 wheels — pads + rotors + fluid", "duration": "2-3 hours",
                       "warranty": "6 months / 10,000 km"},
        "is_active": True, "created_at": datetime.utcnow(),
    },
    {
        "item_id": str(uuid4()), "tenant_id": "tenant_b", "name": "Repair Diagram",
        "image_url": _u("repair_diagram.jpg"),
        "ai_description": "Engine bay reference diagram showing key service points: oil filter, air filter, battery, coolant and brake fluid locations. Handy guide for what we inspect.",
        "price": "Reference",
        "attributes": {"type": "reference diagram"},
        "is_active": True, "created_at": datetime.utcnow(),
    },
]


async def seed_catalog_if_empty() -> None:
    db = get_db()
    count = await db.catalog_items.count_documents({})
    if count == 0:
        await db.catalog_items.insert_many(CATALOG)
        await db.catalog_items.create_index("tenant_id")
        print(f"Seeded {len(CATALOG)} catalog items")
    else:
        print(f"Catalog items already seeded ({count} found)")
