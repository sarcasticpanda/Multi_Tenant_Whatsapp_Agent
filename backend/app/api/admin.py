"""
Admin API — lets a business owner manage tenants, their media library, catalog
items and knowledge base, and upload images/PDFs (stored in GridFS).

After any change that affects RAG (catalog/knowledge), we rebuild the Chroma index
so search reflects the update immediately.
"""
import logging
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.config import settings
from app.db.mongodb import get_db
from app.storage import gridfs
from app.rag.chroma_client import build_chroma_index, index_upsert, index_remove, catalog_doc_text

router = APIRouter(prefix="/api/admin")
logger = logging.getLogger(__name__)


MAX_UPLOAD_MB = 18  # keep memory in check on a small instance


def _check_upload_size(data: bytes, filename: str) -> None:
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            413,
            f"“{filename}” is {len(data) // (1024*1024)} MB — too large (max {MAX_UPLOAD_MB} MB). "
            "Please use a smaller PDF so indexing stays fast and memory-safe.",
        )


async def _cleanup_files_bg(urls: list[str]) -> None:
    """Delete many GridFS blobs off-request (bulk removals can be hundreds of files)."""
    for url in urls:
        await _delete_gridfs_if_owned(url)


async def _start_ingest_job(tenant_id: str, filename: str) -> str:
    """Create a live progress record the dashboard can poll while indexing runs."""
    job_id = str(uuid4())
    await get_db().ingest_jobs.insert_one({
        "job_id": job_id, "tenant_id": tenant_id, "filename": filename,
        "status": "processing", "phase": "starting",
        "images_found": 0, "items_created": 0, "text_chunks": 0,
        "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
    })
    return job_id


async def _ingest_pdf_bg(tenant_id: str, data: bytes, filename: str, job_id: str) -> None:
    """Run the (potentially slow) PDF ingestion off the request so the upload returns
    immediately and large catalogs don't hang the dashboard or block webhooks."""
    try:
        from app.rag.pdf_extractor import ingest_pdf_full
        result = await ingest_pdf_full(tenant_id, data, filename, job_id=job_id)
        logger.info(f"[INGEST] {filename}: {result}")
    except Exception as e:
        logger.error(f"Background PDF ingest failed for {filename}: {e}", exc_info=True)
        await get_db().ingest_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "error", "error": str(e)[:200], "updated_at": datetime.utcnow()}},
        )


async def _delete_gridfs_if_owned(url: str) -> None:
    """If a URL points to a GridFS file (/files/<id>), delete the underlying file so
    removing an item doesn't leave an orphaned blob in the database."""
    if not url or "/files/" not in url:
        return
    file_id = url.split("?")[0].rstrip("/").split("/files/")[-1].split(".")[0]
    try:
        await gridfs.delete_file(file_id)
    except Exception as e:
        logger.warning(f"GridFS cleanup failed for {url}: {e}")


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
    background_tasks: BackgroundTasks,
    keyword: str = Form(...),
    file: UploadFile = File(...),
):
    db = get_db()
    tenant = await db.tenants.find_one({"tenant_id": tenant_id})
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    data = await file.read()
    _check_upload_size(data, file.filename)
    file_id = await gridfs.upload_bytes(
        data, file.filename, file.content_type or "application/octet-stream",
        {"tenant_id": tenant_id, "keyword": keyword},
    )
    url = gridfs.public_url(file_id, file.filename)
    await db.tenants.update_one(
        {"tenant_id": tenant_id}, {"$set": {f"media_library.{keyword.lower()}": url}}
    )

    # If it's a PDF, ALSO index its contents in the background so the bot can both SEND
    # it and ANSWER about it: page text -> knowledge, product images -> catalog.
    # Done off-request so a large catalog doesn't hang the upload.
    ctype = (file.content_type or "").lower()
    fname = (file.filename or "").lower()
    indexing = "pdf" in ctype or fname.endswith(".pdf")
    job_id = None
    if indexing:
        job_id = await _start_ingest_job(tenant_id, file.filename)
        background_tasks.add_task(_ingest_pdf_bg, tenant_id, data, file.filename, job_id)

    return {"ok": True, "keyword": keyword.lower(), "url": url, "indexing": indexing, "job_id": job_id}


@router.delete("/tenants/{tenant_id}/media/{keyword}")
async def admin_remove_media(tenant_id: str, keyword: str):
    db = get_db()
    tenant = await db.tenants.find_one({"tenant_id": tenant_id})
    url = (tenant or {}).get("media_library", {}).get(keyword.lower(), "")
    # Only delete the stored blob if no OTHER keyword points to the same file.
    others = [k for k, u in (tenant or {}).get("media_library", {}).items()
              if u == url and k != keyword.lower()]
    if url and not others:
        await _delete_gridfs_if_owned(url)
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
    # A catalog product is a searchable IMAGE. Reject PDFs/other docs here — they
    # belong in Media (send-by-keyword) or the 'Import catalog PDF' tool (extracts images).
    ctype = (file.content_type or "").lower()
    fname = (file.filename or "").lower()
    is_image = ctype.startswith("image/") or fname.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
    if not is_image:
        raise HTTPException(
            400,
            "A product needs an image (JPG/PNG). For a PDF, use the Media tab (send-by-keyword) "
            "or 'Import a catalog PDF' to auto-extract product images.",
        )
    data = await file.read()
    file_id = await gridfs.upload_bytes(
        data, file.filename, file.content_type or "image/jpeg",
        {"tenant_id": tenant_id, "catalog": name},
    )
    image_url = gridfs.public_url(file_id, file.filename)

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
    await index_upsert([{"id": item["item_id"], "document": catalog_doc_text(item),
                         "metadata": {"tenant_id": tenant_id, "type": "catalog", "title": name,
                                      "image_url": image_url, "price": price}}])
    item.pop("_id", None)
    return {"ok": True, "item": {k: v for k, v in item.items() if k != "created_at"}}


@router.post("/tenants/{tenant_id}/catalog/from-pdf")
async def admin_ingest_catalog_pdf(
    tenant_id: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)
):
    """
    Upload ONE catalog PDF -> integrate BOTH layers (in the background, so a big
    catalog doesn't hang the request):
      • product images  -> searchable catalog items (bot can SHOW them)
      • page text       -> knowledge chunks (bot can ANSWER about the contents)
    Products/knowledge appear in the dashboard as they're indexed.
    """
    db = get_db()
    if not await db.tenants.find_one({"tenant_id": tenant_id}):
        raise HTTPException(404, "Tenant not found")
    data = await file.read()
    _check_upload_size(data, file.filename)
    job_id = await _start_ingest_job(tenant_id, file.filename)
    background_tasks.add_task(_ingest_pdf_bg, tenant_id, data, file.filename, job_id)
    return {"ok": True, "status": "processing", "job_id": job_id,
            "note": "Indexing in the background — products and knowledge will appear shortly."}


@router.get("/tenants/{tenant_id}/ingest-status")
async def admin_ingest_status(tenant_id: str):
    """Latest PDF-ingestion progress for this tenant (polled by the dashboard)."""
    db = get_db()
    job = await db.ingest_jobs.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}, sort=[("updated_at", -1)]
    )
    if job:
        for k in ("created_at", "updated_at"):
            if job.get(k):
                job[k] = job[k].isoformat()
    return {"job": job}


@router.delete("/tenants/{tenant_id}/catalog/by-source")
async def admin_delete_catalog_by_source(
    tenant_id: str, source_pdf: str, background_tasks: BackgroundTasks
):
    """Remove every product that came from one imported PDF. Deletes the records (and
    rebuilds the index) immediately; cleans up the image blobs in the background so a
    large set (hundreds of files) can't time out the request."""
    db = get_db()
    q = {"tenant_id": tenant_id, "attributes.source_pdf": source_pdf}
    docs = await db.catalog_items.find(q, {"image_url": 1, "item_id": 1}).to_list(None)
    urls = [it.get("image_url", "") for it in docs]
    res = await db.catalog_items.delete_many(q)
    await index_remove([it["item_id"] for it in docs])      # incremental, fast
    background_tasks.add_task(_cleanup_files_bg, urls)
    return {"ok": True, "deleted": res.deleted_count}


@router.delete("/catalog/{item_id}")
async def admin_delete_catalog_item(item_id: str):
    db = get_db()
    item = await db.catalog_items.find_one({"item_id": item_id})
    if item:
        await _delete_gridfs_if_owned(item.get("image_url", ""))
    await db.catalog_items.delete_one({"item_id": item_id})
    await index_remove([item_id])
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


@router.post("/tenants/{tenant_id}/knowledge/from-pdf")
async def admin_ingest_knowledge_pdf(tenant_id: str, file: UploadFile = File(...)):
    """
    Upload a PDF as KNOWLEDGE: extract its text, chunk it, embed it — so the bot can
    answer questions about the document's contents (document RAG).
    """
    from app.rag.pdf_extractor import ingest_text_pdf
    db = get_db()
    if not await db.tenants.find_one({"tenant_id": tenant_id}):
        raise HTTPException(404, "Tenant not found")
    data = await file.read()
    summary = await ingest_text_pdf(tenant_id, data, file.filename)
    return {"ok": True, **summary}


@router.post("/knowledge")
async def admin_add_knowledge(body: KnowledgeIn):
    db = get_db()
    doc = body.model_dump()
    doc["doc_id"] = str(uuid4())
    doc["source"] = "admin"
    doc["created_at"] = datetime.utcnow()
    await db.knowledge_docs.insert_one(doc)
    await index_upsert([{"id": doc["doc_id"], "document": doc["content"],
                         "metadata": {"tenant_id": doc["tenant_id"], "type": "knowledge", "title": doc["title"]}}])
    return {"ok": True, "doc_id": doc["doc_id"]}


@router.delete("/knowledge/{doc_id}")
async def admin_delete_knowledge(doc_id: str):
    db = get_db()
    await db.knowledge_docs.delete_one({"doc_id": doc_id})
    await index_remove([doc_id])
    return {"ok": True}


@router.delete("/tenants/{tenant_id}/knowledge/by-source")
async def admin_delete_knowledge_by_source(tenant_id: str, source_pdf: str):
    """Remove every chunk that came from one imported PDF in a single action."""
    db = get_db()
    q = {"tenant_id": tenant_id, "source_pdf": source_pdf}
    ids = [d["doc_id"] for d in await db.knowledge_docs.find(q, {"doc_id": 1}).to_list(None)]
    res = await db.knowledge_docs.delete_many(q)
    await index_remove(ids)
    return {"ok": True, "deleted": res.deleted_count}


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
