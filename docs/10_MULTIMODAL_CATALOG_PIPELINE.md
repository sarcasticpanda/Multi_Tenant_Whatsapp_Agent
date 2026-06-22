# Spec: Multimodal Catalog Ingestion Pipeline (Enhancement)

> Status: PLANNED (not yet built). This is an advanced enhancement, NOT required by the
> assignment. Build only after core deliverables (frontend, deploy, demo) are done.

## Goal

Let a tenant upload a single catalogue PDF. The system automatically:
1. Extracts every product image from the PDF
2. Uses Gemini Vision to describe each image
3. Stores image + description, makes each image individually searchable
4. So a customer can say "show me a green velvet sofa" and the bot sends that exact image —
   even though no one manually tagged it.

This turns a flat PDF into a searchable, multimodal product database.

---

## Why This Is NOT Plain RAG

| Misconception | Reality |
|---------------|---------|
| "RAG extracts images from PDFs" | RAG only embeds/searches TEXT. It cannot see images. |
| "Just point RAG at the PDF" | You must first extract images + generate text descriptions. |

RAG is step 4 of 5. The first 3 steps are a preprocessing pipeline that PRODUCES text
(descriptions) which RAG can then index.

---

## Architecture

```
Tenant uploads catalogue.pdf
          │
          ▼
┌──────────────────────────────────────────────┐
│ [1] PDF IMAGE EXTRACTION  (PyMuPDF / fitz)    │
│   - open PDF                                  │
│   - for each page: page.get_images()          │
│   - save each image to /static/extracted/     │
│   - also grab page.get_text() near the image  │
│     (caption / product name context)          │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ [2] VISION DESCRIPTION  (Gemini 2.5 Flash)    │
│   - send each image + nearby page text        │
│   - prompt: "Describe this product for search:│
│     type, color, material, style, key features"│
│   - returns: rich text description            │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ [3] STORE  (MongoDB: catalog_items)           │
│   {                                           │
│     item_id, tenant_id,                       │
│     image_url: /static/extracted/p3_img1.jpg, │
│     ai_description: "Emerald velvet 3-seater  │
│        sofa with walnut legs...",             │
│     page_text: "Milano Sofa Rs 1,85,000",     │
│     source_pdf: "catalogue.pdf", page: 3      │
│   }                                           │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ [4] INDEX  (Chroma — THIS is the RAG part)    │
│   - embed ai_description + page_text          │
│   - metadata: { tenant_id, image_url,         │
│       item_id, type: "catalog_image" }        │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ [5] RETRIEVE & SEND  (runtime, in the agent)  │
│   Customer: "show me a green velvet sofa"     │
│   - embed query → Chroma search               │
│     (filter tenant_id, type=catalog_image)    │
│   - top match → get image_url from metadata   │
│   - dispatcher sends THAT image               │
│   - bot caption from description              │
└──────────────────────────────────────────────┘
```

---

## New Files / Changes Required

```
backend/app/rag/
├── pdf_extractor.py        # NEW: PyMuPDF image + text extraction
├── catalog_ingest.py       # NEW: orchestrates extract → describe → store → index
└── chroma_client.py        # MODIFY: add a second logical index for catalog_images

backend/app/db/models.py    # MODIFY: add CatalogItemModel

backend/app/api/admin.py    # NEW: POST /api/admin/tenants/{id}/upload-catalog
                            #      (accepts PDF, runs ingest pipeline)

backend/app/agent/tools.py  # MODIFY: add search_catalog_image tool
backend/app/agent/nodes.py  # MODIFY: handle search_catalog_image in LLM node
```

---

## New Dependencies

```
PyMuPDF==1.24.10      # fitz — PDF image + text extraction
Pillow                # already pulled by other deps — image handling
```

---

## Detailed Step Implementations

### Step 1 — pdf_extractor.py

```python
import fitz  # PyMuPDF
import os
from uuid import uuid4

def extract_images_and_text(pdf_path: str, out_dir: str) -> list[dict]:
    """
    Returns list of { image_path, page_number, page_text }.
    """
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    results = []

    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text()  # all text on this page (captions/prices)
        image_list = page.get_images(full=True)

        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image["ext"]  # png/jpeg

            fname = f"p{page_num}_img{img_index}_{uuid4().hex[:8]}.{ext}"
            fpath = os.path.join(out_dir, fname)
            with open(fpath, "wb") as f:
                f.write(image_bytes)

            results.append({
                "image_path": fpath,
                "image_filename": fname,
                "page_number": page_num,
                "page_text": page_text.strip(),
            })

    doc.close()
    return results
```

### Step 2 + 3 + 4 — catalog_ingest.py

```python
import base64
from google import genai
from google.genai import types
from app.config import settings
from app.db.mongodb import get_db
from app.rag.chroma_client import get_chroma_collection

_client = genai.Client(api_key=settings.gemini_api_key)

async def describe_and_store(tenant_id: str, extracted: list[dict], source_pdf: str):
    db = get_db()
    collection = get_chroma_collection()

    for item in extracted:
        with open(item["image_path"], "rb") as f:
            img_bytes = f.read()

        # Gemini Vision description
        resp = _client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=(
                    f"This image is from a product catalogue. Nearby text: '{item['page_text'][:300]}'. "
                    "Describe the product for search: type, color, material, style, notable features. "
                    "Be concise (2 sentences)."
                )),
            ],
        )
        description = resp.text

        image_url = f"{settings.app_base_url}/static/extracted/{item['image_filename']}"
        item_id = f"cat_{tenant_id}_{item['page_number']}_{item['image_filename']}"

        # Store in MongoDB
        await db.catalog_items.insert_one({
            "item_id": item_id,
            "tenant_id": tenant_id,
            "image_url": image_url,
            "ai_description": description,
            "page_text": item["page_text"],
            "source_pdf": source_pdf,
            "page": item["page_number"],
        })

        # Index in Chroma for RAG search
        collection.upsert(
            ids=[item_id],
            documents=[f"{description}\n{item['page_text']}"],
            metadatas=[{
                "tenant_id": tenant_id,
                "type": "catalog_image",
                "image_url": image_url,
                "item_id": item_id,
            }],
        )
```

### Step 5 — new tool in agent

```python
# tools.py — add:
{
    "name": "search_catalog_image",
    "description": "Search the visual product catalog and send the customer the image that best "
                   "matches what they describe (e.g. 'a green velvet sofa', 'a wooden dining table').",
    "parameters": {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "What the customer is looking for"}
        },
        "required": ["description"],
    },
}

# nodes.py — handle it:
if fn.name == "search_catalog_image":
    query = fn_args.get("description", "")
    results = collection.query(
        query_texts=[query],
        where={"tenant_id": tenant_id, "type": "catalog_image"},
        n_results=1,
        include=["metadatas", "distances"],
    )
    if results["metadatas"] and results["distances"][0][0] < 0.9:
        meta = results["metadatas"][0][0]
        media_url = meta["image_url"]
        media_type = "IMAGE"
```

### Admin upload endpoint — admin.py

```python
@router.post("/api/admin/tenants/{tenant_id}/upload-catalog")
async def upload_catalog(tenant_id: str, file: UploadFile):
    # 1. Save uploaded PDF
    pdf_path = f"static/catalogs/{tenant_id}_{file.filename}"
    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    # 2. Extract images + text
    extracted = extract_images_and_text(pdf_path, f"static/extracted/{tenant_id}")

    # 3. Describe + store + index (run in background — can be slow)
    await describe_and_store(tenant_id, extracted, file.filename)

    return {"status": "ingested", "images_found": len(extracted)}
```

---

## Cost / Performance Notes

- Gemini Vision call per image. A 20-image catalog = 20 vision calls.
  Free tier = 15 req/min → a big catalog needs throttling (sleep between calls) or runs in background.
- Image extraction is fast (PyMuPDF is C-backed).
- Storage: extracted images live in /static/extracted/ — on Render free tier (no disk),
  these would need re-extraction on restart, OR store images in MongoDB GridFS / external bucket.
  For demo: keep PDFs in repo and pre-run extraction.

---

## Effort Estimate

| Task | Time |
|------|------|
| pdf_extractor.py | 30 min |
| catalog_ingest.py | 45 min |
| Tool + node wiring | 30 min |
| Admin upload endpoint | 30 min |
| Testing with real catalog | 45 min |
| **Total** | **~3 hours** |

---

## Decision

Build ONLY if core deliverables (frontend, deploy, demo video) are complete and time remains.
Otherwise: document in README as "designed, partially implemented / future work."
The keyword→URL media library already satisfies the assignment's media requirement.
