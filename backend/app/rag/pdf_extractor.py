"""
PDF catalog ingestion: extract embedded product images + nearby text from a PDF,
describe each image (Gemini Vision, with page-text fallback), store image in GridFS,
and create searchable catalog_items.

This is how "upload one catalog PDF" turns into many searchable products with
image + description + the surrounding price/spec text.
"""
import hashlib
import io
import logging
from uuid import uuid4
from datetime import datetime

import fitz  # PyMuPDF

from app.config import settings
from app.db.mongodb import get_db
from app.storage import gridfs
from app.rag.chroma_client import build_chroma_index, index_upsert, catalog_doc_text

logger = logging.getLogger(__name__)


async def _set_job(job_id: str | None, **fields) -> None:
    """Update the live ingestion-progress record the dashboard polls."""
    if not job_id:
        return
    try:
        await get_db().ingest_jobs.update_one(
            {"job_id": job_id}, {"$set": {**fields, "updated_at": datetime.utcnow()}}
        )
    except Exception:
        pass


def _extract(pdf_bytes: bytes, max_items: int = 60) -> list[dict]:
    """
    Return [{image_bytes, ext, page_number, page_text}] for meaningful product images.
    Filters out tiny icons/thumbnails, dedupes identical images, and caps the count so a
    big catalogue doesn't explode into hundreds of junk 'products'.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out, seen = [], set()
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text().strip()
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                base = doc.extract_image(xref)
            except Exception:
                continue
            data = base["image"]
            # Keep only reasonably sized product photos.
            if len(data) < 15000:                       # skip small (logos, icons, rules)
                continue
            if base.get("width", 0) < 250 or base.get("height", 0) < 250:
                continue                                 # skip thumbnails
            h = hashlib.md5(data).hexdigest()
            if h in seen:                                # skip duplicates (repeated swatches)
                continue
            seen.add(h)
            out.append({
                "image_bytes": data,
                "ext": base.get("ext", "png"),
                "page_number": page_num + 1,
                "page_text": page_text,
            })
            if len(out) >= max_items:
                doc.close()
                return out
    doc.close()
    return out


async def _describe(image_bytes: bytes, page_text: str, use_vision: bool = True) -> tuple[str, str]:
    """
    Returns (name, description). Tries Gemini Vision when use_vision; otherwise (bulk PDF
    import) derives the name/description from the page text — instant and no rate limits.
    """
    # Fallback name/description from the page text
    first_line = next((ln.strip() for ln in page_text.splitlines() if ln.strip()), "Catalog item")
    fallback_name = first_line[:60]
    fallback_desc = page_text[:400] if page_text else first_line

    if not use_vision:
        return fallback_name, fallback_desc

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.gemini_api_key)
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=(
                    f"This image is from a product catalogue. Nearby page text: '{page_text[:300]}'. "
                    "Reply in exactly two lines:\n"
                    "Line 1: a short product name (3-5 words).\n"
                    "Line 2: a search-friendly description covering type, color, material, style."
                )),
            ],
        )
        lines = [l.strip() for l in (resp.text or "").splitlines() if l.strip()]
        if len(lines) >= 2:
            name = lines[0].replace("Line 1:", "").replace("**", "").strip()[:60]
            desc = lines[1].replace("Line 2:", "").strip()
            return name or fallback_name, f"{desc} {page_text[:200]}".strip()
    except Exception as e:
        logger.warning(f"Vision describe failed (using page text): {e}")

    return fallback_name, fallback_desc


def extract_pdf_text(pdf_bytes: bytes, max_chars: int = 4000) -> str:
    """Plain concatenated text of a PDF (page by page), capped. Used to give the LLM
    the contents of a customer-sent document so it can answer in the same turn."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning(f"extract_pdf_text: could not open PDF: {e}")
        return ""
    parts = []
    total = 0
    for pno in range(len(doc)):
        t = doc[pno].get_text().strip()
        if not t:
            continue
        parts.append(t)
        total += len(t)
        if total >= max_chars:
            break
    doc.close()
    return " ".join(" ".join(parts).split())[:max_chars]


def _chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into overlapping ~800-char chunks for embedding."""
    text = " ".join(text.split())
    chunks, i = [], 0
    while i < len(text):
        chunk = text[i:i + size].strip()
        if chunk:
            chunks.append(chunk)
        i += size - overlap
    return chunks


async def ingest_text_pdf(tenant_id: str, pdf_bytes: bytes, source_name: str, rebuild: bool = True, job_id: str | None = None) -> dict:
    """
    DOCUMENT RAG: read a PDF's TEXT (page by page), chunk it, and store each chunk as a
    knowledge_doc so the bot can answer questions about the document's contents.
    (Different from ingest_catalog_pdf, which extracts product IMAGES.)
    """
    MAX_CHUNKS = 150  # cap so a huge PDF can't bloat the index / blow Railway's memory
    db = get_db()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = len(doc)
    base = source_name.rsplit(".", 1)[0][:50]
    await _set_job(job_id, phase="text", pages=pages)
    created = 0
    rows = []
    for pno in range(pages):
        if created >= MAX_CHUNKS:
            break
        text = doc[pno].get_text().strip()
        if not text:
            continue
        for ci, chunk in enumerate(_chunk_text(text)):
            doc_id = str(uuid4())
            title = f"{base} · p{pno + 1}" + (f".{ci + 1}" if ci else "")
            await db.knowledge_docs.insert_one({
                "doc_id": doc_id, "tenant_id": tenant_id, "doc_type": "document",
                "title": title, "content": chunk, "source": "pdf",
                "source_pdf": source_name, "created_at": datetime.utcnow(),
            })
            rows.append({"id": doc_id, "document": chunk,
                         "metadata": {"tenant_id": tenant_id, "type": "knowledge", "title": title}})
            created += 1
            if created % 15 == 0:
                await _set_job(job_id, text_chunks=created)
            if created >= MAX_CHUNKS:
                break
    doc.close()
    await _set_job(job_id, text_chunks=created)
    if rebuild:                       # incremental upsert — NO full rebuild
        await index_upsert(rows)
    note = "" if created else "No selectable text found — this PDF may be scanned images."
    preview = extract_pdf_text(pdf_bytes)
    return {"pages": pages, "text_chunks": created, "note": note, "preview": preview}


async def ingest_pdf_full(tenant_id: str, pdf_bytes: bytes, source_name: str, job_id: str | None = None) -> dict:
    """
    One upload, BOTH layers integrated:
      • product IMAGES  -> searchable catalog items (so the bot can SHOW them)
      • page TEXT       -> knowledge chunks (so the bot can ANSWER about the contents)
    Rebuilds the RAG index once at the end.
    """
    # Each step upserts its own new vectors incrementally (no slow full rebuild).
    cat = await ingest_catalog_pdf(tenant_id, pdf_bytes, source_name, rebuild=True, job_id=job_id)
    await _set_job(job_id, phase="text")
    txt = await ingest_text_pdf(tenant_id, pdf_bytes, source_name, rebuild=True, job_id=job_id)
    await _set_job(job_id, status="done", phase="done")
    return {
        "images_found": cat.get("images_found", 0),
        "items_created": cat.get("items_created", 0),
        "text_chunks": txt.get("text_chunks", 0),
        "note": cat.get("note", "") or txt.get("note", ""),
    }


async def ingest_catalog_pdf(tenant_id: str, pdf_bytes: bytes, source_name: str, rebuild: bool = True, job_id: str | None = None) -> dict:
    """Extract product IMAGES -> searchable catalog items. Returns a summary."""
    db = get_db()
    await _set_job(job_id, phase="images")
    extracted = _extract(pdf_bytes)
    await _set_job(job_id, images_found=len(extracted))
    if not extracted:
        return {"images_found": 0, "items_created": 0,
                "note": "No embedded images found. This PDF may be text-only or scanned."}

    created = 0
    rows = []
    for item in extracted:
        # store image in GridFS
        img_filename = f"catalog_{uuid4().hex[:8]}.{item['ext']}"
        file_id = await gridfs.upload_bytes(
            item["image_bytes"], img_filename,
            f"image/{'jpeg' if item['ext'] in ('jpg', 'jpeg') else item['ext']}",
            {"tenant_id": tenant_id, "source_pdf": source_name},
        )
        image_url = gridfs.public_url(file_id, img_filename)
        # Bulk import: derive name/desc from page text (fast, no per-image Gemini calls).
        name, description = await _describe(item["image_bytes"], item["page_text"], use_vision=False)

        item_id = str(uuid4())
        catalog_doc = {
            "item_id": item_id, "tenant_id": tenant_id, "name": name,
            "image_url": image_url, "ai_description": description,
            "price": "", "attributes": {"source_pdf": source_name, "page": item["page_number"]},
            "is_active": True, "created_at": datetime.utcnow(),
        }
        await db.catalog_items.insert_one(catalog_doc)
        rows.append({"id": item_id, "document": catalog_doc_text(catalog_doc),
                     "metadata": {"tenant_id": tenant_id, "type": "catalog", "title": name,
                                  "image_url": image_url, "price": ""}})
        created += 1
        if created % 3 == 0:
            await _set_job(job_id, items_created=created)

    await _set_job(job_id, items_created=created)
    if rebuild:                       # incremental upsert — NO full rebuild
        await index_upsert(rows)
    return {"images_found": len(extracted), "items_created": created, "_rows": rows}
