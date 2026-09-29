"""
Minimal dashboard login. A single admin password issues a signed token (HMAC).
Protected admin routes check the Authorization: Bearer <token> header.

This is intentionally lightweight — it gates the admin panel (which can delete
tenants) without the overhead of a full user system.
"""
import hmac
import hashlib
import time

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.config import settings

router = APIRouter()

# Fail fast: META_APP_SECRET signs admin tokens. If it is missing/empty the app
# must refuse to boot — never silently sign tokens with an insecure default.
if not settings.meta_app_secret:
    raise RuntimeError(
        "META_APP_SECRET is not set — refusing to start. Set a strong random "
        "value in the environment; token signing must never use a default."
    )
_SECRET = settings.meta_app_secret.encode()


def _make_token() -> str:
    issued = str(int(time.time()))
    sig = hmac.new(_SECRET, issued.encode(), hashlib.sha256).hexdigest()
    return f"{issued}.{sig}"


# Simple in-memory login rate limit: max 10 attempts per 5 minutes per IP.
# (Single-instance demo backend; resets on redeploy.)
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_WINDOW_S = 300
_LOGIN_MAX_ATTEMPTS = 10


def _client_ip(request: Request) -> str:
    """Proxy-aware client IP for rate limiting: first entry of X-Forwarded-For
    (the original client, set by Railway/Render), else the socket peer."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _login_rate_ok(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _LOGIN_ATTEMPTS.get(ip, []) if now - t < _LOGIN_WINDOW_S]
    if len(hits) >= _LOGIN_MAX_ATTEMPTS:
        _LOGIN_ATTEMPTS[ip] = hits
        return False
    hits.append(now)
    _LOGIN_ATTEMPTS[ip] = hits
    return True


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
async def login(body: LoginIn, request: Request):
    ip = _client_ip(request)
    if not _login_rate_ok(ip):
        raise HTTPException(status_code=429, detail="Too many attempts, try again later")
    if not hmac.compare_digest(body.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    return {"token": _make_token()}
