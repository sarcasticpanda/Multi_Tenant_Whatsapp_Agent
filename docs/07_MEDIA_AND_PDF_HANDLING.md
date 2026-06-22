# Media Handling — Images, PDFs, Video, OCR

## What the Assignment Actually Requires

| Media Type | Direction | Purpose | Required? |
|-----------|-----------|---------|-----------|
| PDF (catalog, invoice) | Bot → Customer | Send as document attachment | YES |
| Image (sofa, showroom, repair diagram) | Bot → Customer | Send as image attachment | YES |
| Image sent by customer | Customer → Bot | Analyze with Gemini Vision | BONUS B2 |
| Video | Any | Not mentioned in assignment | NO — skip |
| Customer-sent PDF | Customer → Bot | Not mentioned | NO — skip |
| Audio | Any | Not mentioned | NO — skip |

---

## PDFs — No OCR Needed. Here is Why.

### Two completely separate uses of PDFs:

**Use 1: Sending PDFs to customers (bot → customer)**
```
Tenant A has furniture_catalog.pdf stored in backend/static/
Bot sends it via WhatsApp document message
Customer downloads it on their phone

NO OCR NEEDED — we just send the file URL to Meta API
Meta downloads it and sends it to the customer
We never read the PDF content ourselves
```

**Use 2: PDF content in RAG knowledge base**
```
We need the TEXT from PDFs to be searchable in Chroma RAG
Two options:
  A) We MANUALLY write the content (what we do for the demo seed data)
  B) We parse the PDF using pypdf and extract text automatically
```

### For the Demo: Manual Text (No OCR)
The tenant knowledge docs are hand-written text in `seed_knowledge.py`.
This is fine for the demo — the evaluator doesn't check how the text got into Chroma.

### For Production / Bonus: Auto PDF Text Extraction

```python
# pip install pypdf
from pypdf import PdfReader

def extract_text_from_pdf(pdf_path: str) -> list[str]:
    """
    Extracts text from PDF and splits into chunks.
    Each chunk = ~500 characters to fit embedding model.
    No OCR needed for text-based PDFs (standard catalogs, invoices).
    """
    reader = PdfReader(pdf_path)
    chunks = []
    
    for page in reader.pages:
        text = page.extract_text()
        if text:
            # Split page into ~500 char chunks with 50 char overlap
            words = text.split()
            current_chunk = []
            current_len = 0
            
            for word in words:
                current_chunk.append(word)
                current_len += len(word) + 1
                
                if current_len >= 500:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = current_chunk[-10:]  # overlap
                    current_len = sum(len(w) + 1 for w in current_chunk)
            
            if current_chunk:
                chunks.append(" ".join(current_chunk))
    
    return chunks
```

**When is OCR needed?**
OCR is only needed for SCANNED PDFs (images of documents, not text-based PDFs).
For this assignment, all our PDFs are text-based (catalogs, invoices we create).
`pypdf` handles them fine. No OCR (Tesseract, etc.) needed.

---

## Images — Bot Sending to Customer

Simple URL send — no processing needed:

```python
# sofa.jpg stored in backend/static/
# Served at: https://yourapp.onrender.com/static/sofa.jpg
# Meta downloads from this URL and sends to customer
await send_image_message(phone_number_id, customer_phone, image_url)
```

**Image format requirements (Meta):**
- JPG, PNG, WEBP — supported
- Max size: 5MB
- Must be publicly accessible HTTPS URL (localhost fails)

**What images we need (pre-made, stored in backend/static/):**
```
Tenant A:
  sofa.jpg         — any luxury sofa image from Unsplash (free)
  showroom.png     — any furniture showroom image from Unsplash
  
Tenant B:
  repair_diagram.jpg — any car engine diagram from Unsplash
```

Source: Use Unsplash free images for demo. Download and save into backend/static/.

---

## Images — Customer Sending to Bot (Bonus B2)

When customer sends an image, Meta gives you a `media_id` not a URL.
You must fetch the URL first, then pass to Gemini Vision.

```python
async def handle_inbound_image(media_id: str, customer_phone: str) -> str:
    """
    Full pipeline for customer-sent image analysis.
    Returns text description to include in LLM context.
    """
    # Step 1: Get downloadable URL from Meta
    media_url = await get_media_url(media_id)
    # URL expires in 5 minutes — must use immediately
    
    # Step 2: Download image bytes
    async with httpx.AsyncClient() as client:
        img_response = await client.get(
            media_url,
            headers={"Authorization": f"Bearer {settings.META_ACCESS_TOKEN}"}
        )
        img_bytes = img_response.content
    
    # Step 3: Send to Gemini Vision (free, multimodal)
    import google.generativeai as genai
    import base64
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    img_b64 = base64.b64encode(img_bytes).decode()
    
    response = model.generate_content([
        {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": img_b64
            }
        },
        "Describe this image in detail. Focus on: what product or item is shown, its condition, color, style, and any relevant details that would help a customer service agent understand what the customer is asking about."
    ])
    
    return response.text
    # Returns: "The image shows a beige leather sofa with wooden legs. It appears to be in good condition..."
```

This description then gets added to the LangGraph state and injected into the LLM context:
```
[User sent an image: The image shows a beige leather sofa with wooden legs...]
User says: "Do you have something similar?"
```

---

## Video — Skip Completely

Not mentioned anywhere in the assignment PDF. Skipping video:
- No sending videos to customers
- No receiving videos from customers
- No video processing

---

## Summary Table

| Scenario | Approach | Library | Cost |
|---------|---------|---------|------|
| Send PDF catalog to customer | URL send via Meta API | httpx | Free |
| Send image to customer | URL send via Meta API | httpx | Free |
| Store PDF content in RAG | Write text manually in seed | None | Free |
| Auto-extract PDF text (production) | Parse with pypdf | pypdf | Free |
| Customer sends image (Bonus B2) | Gemini Vision analysis | google-generativeai | Free |
| OCR for scanned PDFs | NOT NEEDED for this demo | — | N/A |
| Video | NOT REQUIRED | — | N/A |

---

## Static Files in Backend

```
backend/
└── static/
    ├── furniture_catalog.pdf    # Download from a free PDF sample site
    ├── sofa.jpg                 # Unsplash: search "luxury sofa" → download
    ├── showroom.png             # Unsplash: search "furniture showroom" → download
    ├── price_list.pdf           # Can reuse furniture_catalog.pdf
    ├── invoice_template.pdf     # Download from invoice template sites
    └── repair_diagram.jpg       # Unsplash: search "car engine diagram" → download
```

Free sources for demo assets:
- Images: unsplash.com (free, no attribution needed for demos)
- PDF samples: smallpdf.com/sample-pdf or any Lorem Ipsum PDF
- Invoice PDFs: invoice-template.com (free download)
