from typing import TypedDict, Optional, Literal


class AgentState(TypedDict):
    # Inbound
    tenant_id: str
    customer_phone: str
    session_id: str
    whatsapp_message_id: str
    inbound_text: str
    inbound_media_id: Optional[str]       # Meta media_id for user-sent image
    inbound_media_type: Optional[str]     # "image", "document", etc.
    inbound_media_filename: Optional[str] # original filename (documents)
    inbound_media_mime: Optional[str]     # original mime type (documents)
    inbound_image_description: Optional[str]  # Gemini Vision output (bonus B2)
    inbound_doc_summary: Optional[str]    # extracted text of a customer-sent PDF (for this turn)

    # Retrieved context (Node 2)
    tenant_config: Optional[dict]
    chat_history: Optional[list]
    rag_chunks: Optional[list]
    catalog_names: Optional[list]         # full catalog inventory (names) for honesty

    # LLM output (Node 3)
    llm_reply: Optional[str]
    media_to_send: Optional[str]          # URL
    media_type: Optional[Literal["IMAGE", "DOCUMENT"]]
    media_filename: Optional[str]         # required for DOCUMENT messages

    # Session
    session_status: Literal[
        "WAITING_FOR_BOT", "AGENT_RESPONDING", "RESOLVED", "NEEDS_HUMAN"
    ]

    # Error
    error: Optional[str]
