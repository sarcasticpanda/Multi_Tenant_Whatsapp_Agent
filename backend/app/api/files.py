from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from app.storage import gridfs

router = APIRouter()


@router.get("/files/{file_ref}")
async def serve_file(file_ref: str):
    """Serves a file stored in GridFS (used by WhatsApp media fetch + dashboard).
    file_ref may carry an extension (e.g. '<id>.pdf') — strip it to get the ObjectId."""
    file_id = file_ref.split(".")[0]
    result = await gridfs.get_file(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    data, content_type, filename = result
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.post("/api/admin/upload")
async def upload_file(
    file: UploadFile = File(...),
    tenant_id: str = Form(...),
):
    """Generic upload endpoint — returns the public URL of the stored file."""
    data = await file.read()
    file_id = await gridfs.upload_bytes(
        data=data,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        metadata={"tenant_id": tenant_id},
    )
    return {"file_id": file_id, "url": gridfs.public_url(file_id, file.filename), "filename": file.filename}
