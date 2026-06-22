# WhatsApp Cloud API Integration

## Meta Setup Checklist (Before Coding)

```
1. Go to developers.facebook.com
2. Create a new App → Business type
3. Add WhatsApp product
4. In WhatsApp > API Setup:
   - Note your TEST PHONE NUMBER (this is your phone_number_id)
   - Note your TEMPORARY ACCESS TOKEN (expires in 24h — for dev)
   - Add your personal WhatsApp number as a test recipient
5. In WhatsApp > Configuration:
   - Set webhook URL: https://yourapp.onrender.com/api/webhooks/whatsapp
   - Set Verify Token: match your META_VERIFY_TOKEN env var
   - Subscribe to: messages, message_reactions
6. For permanent token: create System User in Business Settings
```

---

## API Base URL

```
https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages
```

---

## Method 1: Send Read Receipt

Marks customer message as seen (shows blue ticks on their phone).
Must be called FIRST in Acknowledge Node.

```python
async def send_read_receipt(phone_number_id: str, message_id: str):
    """
    Marks a message as read. Shows blue double tick to customer.
    Called immediately on receiving inbound message.
    """
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id   # Meta's wamid from webhook payload
    }
    await _post(phone_number_id, payload)
```

---

## Method 2: Send Typing Indicator (REQUIRED — from PDF)

```python
async def send_typing_indicator(phone_number_id: str, to: str):
    """
    Shows 'typing...' bubble on customer's WhatsApp screen.
    Called right after read receipt.
    IMPORTANT: Meta typing indicator lasts ~25 seconds then auto-stops.
    It also stops automatically when bot sends any message.
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "typing_indicator",
        "typing_indicator": {
            "type": "text"
        }
    }
    await _post(phone_number_id, payload)
```

**Notes on typing indicator:**
- Auto-stops after ~25 seconds (Meta handles this)
- Also auto-stops when bot sends any message
- Does NOT need a separate "stop" API call
- Call it BEFORE the LLM starts (not after)

---

## Method 3: Send Text Message

```python
async def send_text_message(phone_number_id: str, to: str, text: str):
    """
    Sends plain text. WhatsApp natively renders:
    *bold*  →  bold
    _italics_  →  italics
    ~strikethrough~  →  strikethrough
    ```monospace```  →  monospace
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text
        }
    }
    return await _post(phone_number_id, payload)
```

---

## Method 4: Send Image Message

```python
async def send_image_message(phone_number_id: str, to: str, image_url: str):
    """
    Sends an image. URL must be publicly accessible HTTPS.
    Meta downloads the image, so localhost won't work.
    Supported: JPG, PNG, WEBP (max 5MB)
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "image",
        "image": {
            "link": image_url
        }
    }
    return await _post(phone_number_id, payload)
```

---

## Method 5: Send Document Message

```python
async def send_document_message(
    phone_number_id: str,
    to: str,
    doc_url: str,
    filename: str
):
    """
    Sends a document (PDF, DOCX, XLSX, etc.)
    filename is REQUIRED by Meta — shows as download name on customer's phone.
    URL must be publicly accessible HTTPS.
    Max size: 100MB
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "document",
        "document": {
            "link": doc_url,
            "filename": filename   # e.g., "Furniture_Catalog_2024.pdf"
        }
    }
    return await _post(phone_number_id, payload)
```

---

## Internal HTTP Helper

```python
import httpx

BASE_URL = "https://graph.facebook.com/v20.0"

async def _post(phone_number_id: str, payload: dict) -> dict:
    url = f"{BASE_URL}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
```

---

## Webhook GET: Meta Verification Challenge

```python
@router.get("/api/webhooks/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
):
    """
    Meta calls this to verify your webhook URL.
    Must return hub.challenge as plain text if tokens match.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")
```

---

## Webhook POST: Inbound Message Payload (What Meta Sends)

```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "15550783881",
          "phone_number_id": "123456789012345"
        },
        "contacts": [{
          "profile": {"name": "Customer Name"},
          "wa_id": "919876543210"
        }],
        "messages": [{
          "from": "919876543210",
          "id": "wamid.ABGGFlA5FpafAgo6tHcNmNjKADJEQ3bZE3",
          "timestamp": "1669233778",
          "text": {"body": "Can you send me your catalog?"},
          "type": "text"
        }]
      },
      "field": "messages"
    }]
  }]
}
```

**For image message, the messages[0] looks like:**
```json
{
  "from": "919876543210",
  "id": "wamid.xxx",
  "type": "image",
  "image": {
    "caption": "What is this?",
    "mime_type": "image/jpeg",
    "sha256": "xxx",
    "id": "MEDIA_ID"
  }
}
```

---

## Extracting Media URL (Bonus B2)

When user sends image, Meta gives you a `media_id`. You need a second API call to get the URL:

```python
async def get_media_url(media_id: str) -> str:
    """
    Converts Meta media_id to a downloadable URL.
    Used for bonus B2: analyze user-sent images.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://graph.facebook.com/v20.0/{media_id}",
            headers={"Authorization": f"Bearer {settings.META_ACCESS_TOKEN}"}
        )
        data = response.json()
        return data["url"]  # temporary URL, expires in 5 minutes
```

---

## Bonus B1: X-Hub-Signature-256 Validation

```python
import hmac
import hashlib

def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """
    Validates that webhook actually came from Meta, not a fake request.
    signature_header format: "sha256=<hex_digest>"
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    
    expected_sig = signature_header.split("sha256=")[1]
    actual_sig = hmac.new(
        key=settings.META_APP_SECRET.encode(),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_sig, actual_sig)  # constant-time compare (safe)

# In webhook POST handler:
@router.post("/api/webhooks/whatsapp")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    
    if not verify_webhook_signature(payload_bytes, signature):
        return Response(status_code=403)  # reject fake webhooks
    
    # ... rest of handler
```

---

## Inbound Message Parser

```python
def extract_message(payload: dict) -> dict | None:
    """
    Parses the complex Meta webhook payload into a flat dict.
    Returns None if payload is a status update (not a user message).
    """
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
        
        # Skip status updates (delivered, read receipts from Meta)
        if "statuses" in change:
            return None
        
        messages = change.get("messages", [])
        if not messages:
            return None
        
        message = messages[0]
        phone_number_id = change["metadata"]["phone_number_id"]
        customer_phone = message["from"]
        message_type = message["type"]
        
        text = ""
        media_url = None
        media_type = None
        media_id = None
        
        if message_type == "text":
            text = message["text"]["body"]
        elif message_type == "image":
            media_id = message["image"]["id"]
            text = message["image"].get("caption", "")
            media_type = "image"
        elif message_type == "document":
            media_id = message["document"]["id"]
            text = message["document"].get("caption", "")
            media_type = "document"
        
        return {
            "phone_number_id": phone_number_id,
            "customer_phone": customer_phone,
            "message_id": message["id"],
            "message_type": message_type,
            "text": text,
            "media_id": media_id,
            "media_type": media_type,
            "timestamp": message["timestamp"]
        }
    except (KeyError, IndexError):
        return None
```

---

## Static Files for Tenant Media

These must be real files served at a public HTTPS URL.
On Render, they'll be at `https://yourapp.onrender.com/static/...`

```
backend/static/
├── furniture_catalog.pdf     → Tenant A: "catalog", "brochure"
├── sofa.jpg                  → Tenant A: "sofa", "product"
├── showroom.png              → Tenant A: "showroom"
├── price_list.pdf            → Tenant A: "price list", "pricing"
├── invoice_template.pdf      → Tenant B: "invoice", "service menu"
└── repair_diagram.jpg        → Tenant B: "repair diagram", "diagram"
```

FastAPI static file setup:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")
```
