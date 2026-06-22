"""
GridFS storage — stores uploaded and inbound media files INSIDE MongoDB.

Why GridFS: Render's free tier has no persistent disk, so anything written to
/static is lost on restart. GridFS keeps files in MongoDB (already our database),
so uploads and customer-sent images survive restarts with zero extra services.
"""
import io
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from app.db.mongodb import get_db
from app.config import settings

_bucket: AsyncIOMotorGridFSBucket | None = None


def get_bucket() -> AsyncIOMotorGridFSBucket:
    global _bucket
    if _bucket is None:
        _bucket = AsyncIOMotorGridFSBucket(get_db(), bucket_name="media")
    return _bucket


async def upload_bytes(
    data: bytes,
    filename: str,
    content_type: str,
    metadata: dict | None = None,
) -> str:
    """Store bytes in GridFS. Returns the file_id (str) for building a public URL."""
    bucket = get_bucket()
    meta = {"content_type": content_type, **(metadata or {})}
    file_id = await bucket.upload_from_stream(filename, io.BytesIO(data), metadata=meta)
    return str(file_id)


async def get_file(file_id: str):
    """Returns (bytes, content_type, filename) or None if not found."""
    bucket = get_bucket()
    try:
        stream = await bucket.open_download_stream(ObjectId(file_id))
    except Exception:
        return None
    data = await stream.read()
    meta = stream.metadata or {}
    content_type = meta.get("content_type", "application/octet-stream")
    return data, content_type, stream.filename


async def delete_file(file_id: str) -> bool:
    bucket = get_bucket()
    try:
        await bucket.delete(ObjectId(file_id))
        return True
    except Exception:
        return False


def public_url(file_id: str, filename: str = "") -> str:
    """
    Build the public URL that WhatsApp / the dashboard will fetch.
    Append the original file extension so the type (PDF vs image) is visible from the
    URL — the bot decides image-vs-document and the dashboard picks the icon from it.
    """
    ext = ""
    if filename and "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
    return f"{settings.app_base_url}/files/{file_id}{ext}"
