from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import uuid4


class TenantModel(BaseModel):
    tenant_id: str
    name: str
    system_prompt: str
    whatsapp_phone_number_id: str
    media_library: dict[str, str]  # keyword -> URL
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatSessionModel(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    customer_phone: str
    status: Literal[
        "WAITING_FOR_BOT",
        "AGENT_RESPONDING",
        "RESOLVED",
        "NEEDS_HUMAN"
    ] = "WAITING_FOR_BOT"
    context_vars: dict = Field(default_factory=dict)
    message_count: int = 0
    last_message_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MessageAuditLogModel(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    whatsapp_message_id: str = ""
    session_id: str
    tenant_id: str
    direction: Literal["INBOUND", "OUTBOUND"]
    sender: str  # customer phone or "BOT"
    text_content: str = ""
    media_url: Optional[str] = None
    media_type: Optional[Literal["IMAGE", "DOCUMENT"]] = None
    media_mime_type: Optional[str] = None
    media_filename: Optional[str] = None
    agent_state: Optional[Literal["TYPING", "SENT"]] = None
    is_read: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeDocModel(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    doc_type: Literal["product", "faq", "pricing", "service", "policy"]
    title: str
    content: str
    source: str = "manual"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CatalogItemModel(BaseModel):
    """A visual product/service: image LINKED to structured data, searchable by description."""
    item_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str
    image_url: str
    ai_description: str = ""          # auto-generated (Gemini Vision) or manual; drives search
    price: str = ""
    attributes: dict = Field(default_factory=dict)  # color, material, delivery_days, etc.
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
