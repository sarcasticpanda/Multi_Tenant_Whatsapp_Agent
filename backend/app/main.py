import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.dashboard import router as dashboard_router
from app.api.webhooks import router as webhook_router
from app.api.files import router as files_router
from app.api.admin import router as admin_router
from app.api.auth import router as auth_router, require_admin
from app.db.mongodb import connect_mongodb, close_mongodb
from app.db.seed import seed_tenants_if_empty
from app.db.seed_catalog import seed_catalog_if_empty
from app.rag.chroma_client import ensure_index_ready
from app.rag.seed_knowledge import seed_knowledge_if_empty

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _build_index_bg():
    """Build the RAG index after startup so it never blocks the port/health check."""
    try:
        await ensure_index_ready()
        logger.info("RAG index ready.")
    except Exception as e:
        logger.error(f"RAG index build failed (bot still serves, RAG degraded): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — keep this FAST so the port binds and /health responds immediately.
    logger.info("Starting up...")
    await connect_mongodb()
    await seed_tenants_if_empty()
    await seed_knowledge_if_empty()
    await seed_catalog_if_empty()
    # Build the (heavier) Chroma index in the BACKGROUND — non-blocking.
    asyncio.create_task(_build_index_bg())
    logger.info("Core ready; RAG index building in background.")
    yield
    # Shutdown
    await close_mongodb()
    logger.info("Shutdown complete.")


app = FastAPI(title="Multi-Tenant WhatsApp Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (PDFs, images for tenant media library)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(files_router)
app.include_router(auth_router)
# Admin/management routes require a valid login token.
app.include_router(admin_router, dependencies=[Depends(require_admin)])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "Multi-Tenant WhatsApp Agent API", "docs": "/docs"}
