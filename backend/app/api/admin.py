"""
Admin API — lets a business owner manage tenants, their media library, catalog
items and knowledge base, and upload images/PDFs (stored in GridFS).

After any change that affects RAG (catalog/knowledge), we rebuild the Chroma index
so search reflects the update immediately.
"""
import logging
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.db.mongodb import get_db
from app.storage import gridfs
from app.rag.chroma_client import build_chroma_index

router = APIRouter(prefix="/api/admin")
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Tenants CRUD
# --------------------------------------------------------------------------- #

class TenantIn(BaseModel):
    tenant_id: str
    name: str
    system_prompt: str
    whatsapp_phone_number_id: str | None = None
    media_library: dict[str, str] = {}


@router.get("/tenants")
async def admin_list_tenants():
    db = get_db()
    tenants = await db.tenants.find({}, {"_id": 0}).to_list(None)
    for t in tenants:
        t.pop("whatsapp_access_token", None)
    return {"tenants": tenants}


@router.post("/tenants")
async def admin_create_tenant(body: TenantIn):
    db = get_db()
    if await db.tenants.find_one({"tenant_id": body.tenant_id}):
        raise HTTPException(409, "A tenant with that id already exists")
    doc = body.model_dump()
    doc["whatsapp_phone_number_id"] = doc.get("whatsapp_phone_number_id") or settings.meta_phone_number_id
    doc["is_active"] = True
    doc["created_at"] = datetime.utcnow()
    await db.tenants.insert_one(doc)
    return {"ok": True, "tenant_id": body.tenant_id}


@router.put("/tenants/{tenant_id}")
async def admin_update_tenant(tenant_id: str, body: dict):
    db = get_db()
    body.pop("tenant_id", None)
    body.pop("_id", None)
    res = await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "Tenant not found")
    return {"ok": True}


@router.delete("/tenants/{tenant_id}")
async def admin_delete_tenant(tenant_id: str):
    db = get_db()
    await db.tenants.delete_one({"tenant_id": tenant_id})
    await db.catalog_items.delete_many({"tenant_id": tenant_id})
    await db.knowledge_docs.delete_many({"tenant_id": tenant_id})
    await build_chroma_index()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Customer routing (customer phone -> tenant)
# --------------------------------------------------------------------------- #

class RouteIn(BaseModel):
    customer_phone: str
    tenant_id: str


@router.get("/routing")
async def admin_list_routing():
    """All customer -> tenant assignments, with tenant name for display."""
    db = get_db()
    routes = await db.customer_routing.find({}, {"_id": 0}).to_list(None)
    names = {t["tenant_id"]: t["name"] for t in await db.tenants.find({}, {"_id": 0, "tenant_id": 1, "name": 1}).to_list(None)}
    for r in routes:
        r["tenant_name"] = names.get(r["tenant_id"], r["tenant_id"])
    return {"routes": routes}


@router.post("/routing")
async def admin_set_route(body: RouteIn):
    """Assign (or reassign) a customer phone to a tenant."""
    db = get_db()
    phone = body.customer_phone.strip().lstrip("+").replace(" ", "")
    if not phone:
        raise HTTPException(400, "customer_phone is required")
    if not await db.tenants.find_one({"tenant_id": body.tenant_id}):
        raise HTTPException(404, "Tenant not found")
    await db.customer_routing.update_one(
        {"customer_phone": phone},
        {"$set": {"customer_phone": phone, "tenant_id": body.tenant_id}},
        upsert=True,
    )
    return {"ok": True, "customer_phone": phone, "tenant_id": body.tenant_id}


@router.delete("/routing/{customer_phone}")
async def admin_delete_route(customer_phone: str):
    db = get_db()
    await db.customer_routing.delete_one({"customer_phone": customer_phone.lstrip("+")})
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Media library (keyword -> uploaded file URL)
# --------------------------------------------------------------------------- #

@router.post("/tenants/{tenant_id}/media")
async def admin_add_media(
    tenant_id: str,
    keyword: str = Form(...),
    file: UploadFile = File(...),
):
    db = get_db()
    tenant = await db.tenants.find_one({"tenant_id": tenant_id})
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    data = await file.read()
    file_id = await gridfs.upload_bytes(
        data, file.filename, file.content_type or "application/octet-stream",
        {"tenant_id": tenant_id, "keyword": keyword},
    )
    url = gridfs.public_url(file_id)
    await db.tenants.update_one(
        {"tenant_id": tenant_id}, {"$set": {f"media_library.{keyword.lower()}": url}}
    )
    return {"ok": True, "keyword": keyword.lower(), "url": url}


@router.delete("/tenants/{tenant_id}/media/{keyword}")
async def admin_remove_media(tenant_id: str, keyword: str):
    db = get_db()
    await db.tenants.update_one(
        {"tenant_id": tenant_id}, {"$unset": {f"media_library.{keyword.lower()}": ""}}
    )
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Catalog items (image + data, searchable)
# --------------------------------------------------------------------------- #

@router.get("/tenants/{tenant_id}/catalog")
async def admin_list_catalog(tenant_id: str):
    db = get_db()
    items = await db.catalog_items.find({"tenant_id": tenant_id}, {"_id": 0}).to_list(None)
    return {"items": items}


@router.post("/tenants/{tenant_id}/catalog")
async def admin_add_catalog_item(
    tenant_id: str,
    name: str = Form(...),
    price: str = Form(""),
    description: str = Form(""),
    attributes: str = Form("{}"),
    auto_describe: bool = Form(True),
    file: UploadFile = File(...),
):
    """
    Upload a product image + data. If auto_describe and no description given,
    Gemini Vision generates the searchable description from the image.
    """
    import json
    db = get_db()
    data = await file.read()
    file_id = await gridfs.upload_bytes(
        data, file.filename, file.content_type or "image/jpeg",
        {"tenant_id": tenant_id, "catalog": name},
    )
    image_url = gridfs.public_url(file_id)

    ai_description = description
    if auto_describe and not description:
        ai_description = await _vision_describe(data, name) or name

    try:
        attrs = json.loads(attributes) if attributes else {}
    except Exception:
        attrs = {}

    item = {
        "item_id": str(uuid4()), "tenant_id": tenant_id, "name": name,
        "image_url": image_url, "ai_description": ai_description,
        "price": price, "attributes": attrs, "is_active": True,
        "created_at": datetime.utcnow(),
    }
    await db.catalog_items.insert_one(item)
    await build_chroma_index()  # make it searchable now
    item.pop("_id", None)
    return {"ok": True, "item": {k: v for k, v in item.items() if k != "created_at"}}


@router.post("/tenants/{tenant_id}/catalog/from-pdf")
async def admin_ingest_catalog_pdf(tenant_id: str, file: UploadFile = File(...)):
    """
    Upload ONE catalog PDF -> extract every embedded product image,
    describe each (Gemini Vision, page-text fallback), store in GridFS,
    and create searchable catalog items automatically.
    """
    from app.rag.pdf_extractor import ingest_catalog_pdf
    db = get_db()
    if not await db.tenants.find_one({"tenant_id": tenant_id}):
        raise HTTPException(404, "Tenant not found")
    data = await file.read()
    summary = await ingest_catalog_pdf(tenant_id, data, file.filename)
    return {"ok": True, **summary}


@router.delete("/catalog/{item_id}")
async def admin_delete_catalog_item(item_id: str):
    db = get_db()
    await db.catalog_items.delete_one({"item_id": item_id})
    await build_chroma_index()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Knowledge docs (text FAQ / policy)
# --------------------------------------------------------------------------- #

class KnowledgeIn(BaseModel):
    tenant_id: str
    doc_type: str = "faq"
    title: str
    content: str


@router.get("/tenants/{tenant_id}/knowledge")
async def admin_list_knowledge(tenant_id: str):
    db = get_db()
    docs = await db.knowledge_docs.find({"tenant_id": tenant_id}, {"_id": 0}).to_list(None)
    return {"docs": docs}


@router.post("/knowledge")
async def admin_add_knowledge(body: KnowledgeIn):
    db = get_db()
    doc = body.model_dump()
    doc["doc_id"] = str(uuid4())
    doc["source"] = "admin"
    doc["created_at"] = datetime.utcnow()
    await db.knowledge_docs.insert_one(doc)
    await build_chroma_index()
    return {"ok": True, "doc_id": doc["doc_id"]}


@router.delete("/knowledge/{doc_id}")
async def admin_delete_knowledge(doc_id: str):
    db = get_db()
    await db.knowledge_docs.delete_one({"doc_id": doc_id})
    await build_chroma_index()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Helper: Gemini Vision auto-description
# --------------------------------------------------------------------------- #

async def _vision_describe(image_bytes: bytes, name: str) -> str | None:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.gemini_api_key)
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=(
                    f"This is a product called '{name}'. Write a concise, search-friendly "
                    "description (1-2 sentences) covering type, color, material and style, "
                    "so customers can find it by describing what they want."
                )),
            ],
        )
        return resp.text
    except Exception as e:
        logger.warning(f"Vision auto-describe failed: {e}")
        return None
