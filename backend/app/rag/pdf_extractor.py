"""
PDF catalog ingestion: extract embedded product images + nearby text from a PDF,
describe each image (Gemini Vision, with page-text fallback), store image in GridFS,
and create searchable catalog_items.

This is how "upload one catalog PDF" turns into many searchable products with
image + description + the surrounding price/spec text.
"""
import io
import logging
from uuid import uuid4
from datetime import datetime

import fitz  # PyMuPDF

from app.config import settings
from app.db.mongodb import get_db
from app.storage import gridfs
from app.rag.chroma_client import build_chroma_index

logger = logging.getLogger(__name__)


def _extract(pdf_bytes: bytes) -> list[dict]:
    """Return [{image_bytes, ext, page_number, page_text}] for each embedded image."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out = []
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
            # skip tiny images (logos, icons, separators)
            if len(data) < 6000:
                continue
            out.append({
                "image_bytes": data,
                "ext": base.get("ext", "png"),
                "page_number": page_num + 1,
                "page_text": page_text,
            })
    doc.close()
    return out


async def _describe(image_bytes: bytes, page_text: str) -> tuple[str, str]:
    """
    Returns (name, description). Tries Gemini Vision; falls back to page text.
    """
    # Fallback name/description from the page text
    first_line = next((ln.strip() for ln in page_text.splitlines() if ln.strip()), "Catalog item")
    fallback_name = first_line[:60]
    fallback_desc = page_text[:400] if page_text else first_line

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


async def ingest_catalog_pdf(tenant_id: str, pdf_bytes: bytes, source_name: str) -> dict:
    """Full pipeline. Returns a summary."""
    db = get_db()
    extracted = _extract(pdf_bytes)
    if not extracted:
        return {"images_found": 0, "items_created": 0,
                "note": "No embedded images found. This PDF may be text-only or scanned."}

    created = 0
    for item in extracted:
        # store image in GridFS
        img_filename = f"catalog_{uuid4().hex[:8]}.{item['ext']}"
        file_id = await gridfs.upload_bytes(
            item["image_bytes"], img_filename,
            f"image/{'jpeg' if item['ext'] in ('jpg', 'jpeg') else item['ext']}",
            {"tenant_id": tenant_id, "source_pdf": source_name},
        )
        image_url = gridfs.public_url(file_id, img_filename)
        name, description = await _describe(item["image_bytes"], item["page_text"])

        await db.catalog_items.insert_one({
            "item_id": str(uuid4()), "tenant_id": tenant_id, "name": name,
            "image_url": image_url, "ai_description": description,
            "price": "", "attributes": {"source_pdf": source_name, "page": item["page_number"]},
            "is_active": True, "created_at": datetime.utcnow(),
        })
        created += 1

    await build_chroma_index()  # make all new items searchable
    return {"images_found": len(extracted), "items_created": created}
