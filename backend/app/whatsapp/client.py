import hmac
import hashlib
import httpx
from app.config import settings

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"


async def _post(phone_number_id: str, payload: dict) -> dict:
    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_access_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


async def send_read_receipt(phone_number_id: str, message_id: str) -> dict:
    """Marks customer's message as read (shows blue double ticks)."""
    return await _post(phone_number_id, {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    })


async def send_typing_indicator(phone_number_id: str, message_id: str) -> dict:
    """
    Shows 'typing...' bubble on customer's phone.
    Meta's current API combines mark-as-read + typing indicator in ONE call,
    keyed by the inbound message_id (NOT the recipient phone).
    Auto-stops after ~25s or when the bot sends any message.
    """
    return await _post(phone_number_id, {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {
            "type": "text"
        },
    })


async def send_text_message(phone_number_id: str, to: str, text: str) -> dict:
    """
    Sends plain text. WhatsApp renders *bold*, _italics_, ~strikethrough~ natively.
    """
    return await _post(phone_number_id, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text,
        },
    })


async def send_image_message(phone_number_id: str, to: str, image_url: str) -> dict:
    """
    Sends an image from a public HTTPS URL.
    Meta downloads from URL — must be publicly accessible.
    """
    return await _post(phone_number_id, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "image",
        "image": {
            "link": image_url,
        },
    })


async def send_document_message(
    phone_number_id: str, to: str, doc_url: str, filename: str
) -> dict:
    """
    Sends a document (PDF etc.) with a visible filename on the customer's phone.
    filename is REQUIRED by Meta API spec.
    """
    return await _post(phone_number_id, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "document",
        "document": {
            "link": doc_url,
            "filename": filename,
        },
    })


async def get_media_url(media_id: str) -> str:
    """
    Converts a Meta media_id (from inbound image webhook) to a temporary
    downloadable URL. URL expires in ~5 minutes — use immediately.
    """
    headers = {"Authorization": f"Bearer {settings.meta_access_token}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{GRAPH_API_BASE}/{media_id}", headers=headers
        )
        response.raise_for_status()
        return response.json()["url"]


async def download_media(media_url: str) -> bytes:
    """Downloads media bytes from a Meta temporary URL."""
    headers = {"Authorization": f"Bearer {settings.meta_access_token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(media_url, headers=headers)
        response.raise_for_status()
        return response.content


def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """
    Bonus B1: Validates X-Hub-Signature-256 header.
    Ensures webhook genuinely came from Meta, not a forged request.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = signature_header.split("sha256=", 1)[1]
    actual = hmac.new(
        key=settings.meta_app_secret.encode(),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, actual)  # constant-time — safe against timing attacks
