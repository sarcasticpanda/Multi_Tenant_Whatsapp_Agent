"""
Minimal dashboard login. A single admin password issues a signed token (HMAC).
Protected admin routes check the Authorization: Bearer <token> header.

This is intentionally lightweight — it gates the admin panel (which can delete
tenants) without the overhead of a full user system.
"""
import hmac
import hashlib
import time

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter()

_SECRET = (settings.meta_app_secret or "fallback-secret").encode()


def _make_token() -> str:
    issued = str(int(time.time()))
    sig = hmac.new(_SECRET, issued.encode(), hashlib.sha256).hexdigest()
    return f"{issued}.{sig}"


def verify_token(token: str) -> bool:
    try:
        issued, sig = token.split(".", 1)
        expected = hmac.new(_SECRET, issued.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        # 7-day validity
        return (time.time() - int(issued)) < 7 * 86400
    except Exception:
        return False


def require_admin(authorization: str = Header(default="")):
    """FastAPI dependency — raises 401 unless a valid bearer token is present."""
    token = authorization.replace("Bearer ", "").strip()
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True


class LoginIn(BaseModel):
    password: str


@router.post("/api/login")
async def login(body: LoginIn):
    if not hmac.compare_digest(body.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    return {"token": _make_token()}
