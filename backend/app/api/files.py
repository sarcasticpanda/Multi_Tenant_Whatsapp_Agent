from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from app.storage import gridfs
from app.api.admin import _check_upload_size
from app.api.auth import require_admin
import re

router = APIRouter()

# Public by design: file_ref is a random Mongo ObjectId (unguessable URL),
# and WhatsApp's servers + dashboard <img> tags fetch these without auth headers.

# Only these stored content types are ever served inline. Anything else is
# forced to an attachment download with a generic type, so a stored SVG/HTML
# can never execute as active content in a visitor's browser.
_INLINE_MIME_ALLOWLIST = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf", "video/mp4", "audio/mpeg", "audio/ogg",
    "text/plain",
}


@router.get("/files/{file_ref}")
async def serve_file(file_ref: str):
    """Serves a file stored in GridFS (used by WhatsApp media fetch + dashboard).
    file_ref may carry an extension (e.g. '<id>.pdf') — strip it to get the ObjectId."""
    file_id = file_ref.split(".")[0]
    result = await gridfs.get_file(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    data, content_type, filename = result
    # Sanitize filename for the Content-Disposition header (header-injection safe):
    # whitelist chars, then explicitly strip anything that could break out of the
    # quoted filename (path separators, quotes, newlines).
    safe_name = re.sub(r"[^\w.\- ]", "_", filename or "file")[:120]
    safe_name = (safe_name.replace("/", "_").replace("\\", "_")
                          .replace('"', "_").replace("\n", "").replace("\r", ""))
    if content_type in _INLINE_MIME_ALLOWLIST:
        media_type = content_type
        disposition = f'inline; filename="{safe_name}"'
    else:
        # Unknown/untrusted type — download only, never rendered inline.
        media_type = "application/octet-stream"
        disposition = f'attachment; filename="{safe_name}"'
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/api/admin/upload", dependencies=[Depends(require_admin)])
async def upload_file(
    file: UploadFile = File(...),
    tenant_id: str = Form(...),
):
    """Generic upload endpoint — admin only. Returns the public URL of the stored file."""
    data = await file.read()
    _check_upload_size(data, file.filename)
    file_id = await gridfs.upload_bytes(
        data=data,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        metadata={"tenant_id": tenant_id},
    )
    return {"file_id": file_id, "url": gridfs.public_url(file_id, file.filename), "filename": file.filename}
