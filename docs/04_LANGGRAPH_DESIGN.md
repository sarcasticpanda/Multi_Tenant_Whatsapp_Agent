# LangGraph Agent Design

## LLM Decision (LOCKED)

```
Primary:    Google Gemini 2.5 Flash
Model ID:   gemini-2.5-flash
API:        Google AI Studio (free tier)
Rate limit: 15 RPM, 1,500 RPD, 1M TPM
Tool call:  YES — full function calling
Vision:     YES — handles inbound image parsing (bonus B2)
Context:    1M tokens

Fallback:   Groq llama-3.3-70b-versatile (if Gemini rate limited)
API:        Groq Cloud (free tier)
Rate limit: 30 RPM, 1K RPD — use sparingly

Embeddings: sentence-transformers/all-MiniLM-L6-v2
Cost:       FREE — runs locally in FastAPI process
```

---

## AgentState Schema

```python
# app/agent/state.py

from typing import TypedDict, Optional, Literal

class AgentState(TypedDict):
    # Inbound message info
    tenant_id: str
    customer_phone: str
    session_id: str
    whatsapp_message_id: str       # Meta's wamid for read receipt
    inbound_text: str
    inbound_media_url: Optional[str]    # if user sent image (bonus B2)
    inbound_media_type: Optional[str]   # "image", "document", etc.
    inbound_image_description: Optional[str]  # after Gemini Vision analysis (bonus B2)
    
    # Retrieved context (populated by Node 2)
    tenant_config: Optional[dict]      # full tenant doc from MongoDB
    chat_history: Optional[list]       # last 5 messages
    rag_chunks: Optional[list[str]]    # relevant knowledge chunks
    
    # LLM output (populated by Node 3)
    llm_reply: Optional[str]           # text to send to customer
    media_to_send: Optional[str]       # URL of image/doc to send
    media_type: Optional[Literal["IMAGE", "DOCUMENT"]]
    media_filename: Optional[str]      # for document messages (required by Meta)
    
    # Session management
    session_status: Literal[
        "WAITING_FOR_BOT",
        "AGENT_RESPONDING",
        "RESOLVED",
        "NEEDS_HUMAN"
    ]
    
    # Error handling
    error: Optional[str]
```

---

## Tool Definitions (for Gemini Function Calling)

```python
# app/agent/tools.py

TOOLS = [
    {
        "name": "get_media",
        "description": "Fetch a media file (image or document) from the tenant's media library based on a keyword. Use this when the customer asks for a catalog, product image, invoice, repair diagram, price list, or any visual asset.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "The keyword to look up in the media library (e.g., 'catalog', 'sofa', 'invoice', 'repair diagram')"
                }
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "search_knowledge",
        "description": "Search the knowledge base for additional information to answer the customer's question. Use this when you need more details about products, services, policies, or FAQs.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant knowledge base articles"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "escalate_to_human",
        "description": "Escalate this conversation to a human agent. Use this ONLY when the customer expresses clear frustration, anger, or distress, or when the query is completely outside your knowledge and capability.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief reason for escalation (e.g., 'Customer expressed frustration about delayed delivery')"
                }
            },
            "required": ["reason"]
        }
    }
]
```

---

## Node 1: Acknowledge Node

```python
# Purpose: Instantly fires UX signals to WhatsApp, saves inbound message
# Side effects: read receipt, typing indicator ON, MongoDB write

async def acknowledge_node(state: AgentState) -> AgentState:
    # 1. Send read receipt (marks message as seen — blue ticks)
    await whatsapp_client.send_read_receipt(
        phone_number_id=state["tenant_config"]["whatsapp_phone_number_id"],
        message_id=state["whatsapp_message_id"]
    )
    
    # 2. Send typing indicator ON
    await whatsapp_client.send_typing_indicator(
        phone_number_id=state["tenant_config"]["whatsapp_phone_number_id"],
        to=state["customer_phone"]
    )
    
    # 3. Save inbound message to MongoDB
    await db.message_audit_log.insert_one({
        "message_id": str(uuid4()),
        "whatsapp_message_id": state["whatsapp_message_id"],
        "session_id": state["session_id"],
        "tenant_id": state["tenant_id"],
        "direction": "INBOUND",
        "sender": state["customer_phone"],
        "text_content": state["inbound_text"],
        "media_url": state["inbound_media_url"],
        "media_type": state.get("inbound_media_type"),
        "agent_state": "TYPING",
        "is_read": True,
        "timestamp": datetime.utcnow()
    })
    
    # 4. Update session status
    await db.chat_sessions.update_one(
        {"session_id": state["session_id"]},
        {"$set": {"status": "AGENT_RESPONDING", "last_message_at": datetime.utcnow()}}
    )
    
    state["session_status"] = "AGENT_RESPONDING"
    return state
```

---

## Node 2: Context Retriever Node

```python
# Purpose: Pulls everything the LLM needs to reason
# Reads from: MongoDB (tenant + history), Chroma (RAG)

async def context_retriever_node(state: AgentState) -> AgentState:
    tenant_id = state["tenant_id"]
    
    # 1. Fetch tenant config
    tenant = await db.tenants.find_one({"tenant_id": tenant_id})
    state["tenant_config"] = tenant
    
    # 2. Fetch last 5 messages (chronological)
    messages = await db.message_audit_log.find(
        {"session_id": state["session_id"]}
    ).sort("timestamp", -1).limit(5).to_list(5)
    state["chat_history"] = list(reversed(messages))
    
    # 3. RAG search (filtered by tenant_id)
    rag_chunks = search_knowledge_base(
        query=state["inbound_text"],
        tenant_id=tenant_id
    )
    state["rag_chunks"] = rag_chunks
    
    # BONUS B2: If inbound image, analyze with Gemini Vision
    if state.get("inbound_media_url"):
        description = await analyze_image_with_gemini(state["inbound_media_url"])
        state["inbound_image_description"] = description
    
    return state
```

---

## Node 3: LLM Reasoning Node

```python
# Purpose: Core AI reasoning. Decides reply + whether to send media
# LLM: Gemini 2.5 Flash with 3 tools

async def llm_reasoning_node(state: AgentState) -> AgentState:
    tenant = state["tenant_config"]
    
    # Build system prompt
    system_prompt = build_system_prompt(
        tenant_prompt=tenant["system_prompt"],
        rag_chunks=state["rag_chunks"]
    )
    
    # Build conversation history for LLM
    messages = []
    for msg in state["chat_history"][:-1]:  # exclude current message
        role = "user" if msg["direction"] == "INBOUND" else "model"
        messages.append({"role": role, "parts": [{"text": msg["text_content"]}]})
    
    # Current user message (with image description if available)
    user_content = state["inbound_text"]
    if state.get("inbound_image_description"):
        user_content = f"[User sent an image: {state['inbound_image_description']}]\n{user_content}"
    
    messages.append({"role": "user", "parts": [{"text": user_content}]})
    
    # Call Gemini with tools
    response = gemini_client.generate_content(
        contents=messages,
        system_instruction=system_prompt,
        tools=[{"function_declarations": TOOLS}],
        tool_config={"function_calling_config": {"mode": "AUTO"}}
    )
    
    # Handle tool calls
    media_url = None
    media_type = None
    media_filename = None
    final_reply = None
    
    for part in response.candidates[0].content.parts:
        if hasattr(part, "function_call"):
            tool_name = part.function_call.name
            args = dict(part.function_call.args)
            
            if tool_name == "get_media":
                keyword = args["keyword"].lower()
                # Look up in tenant's media_library
                for key, url in tenant["media_library"].items():
                    if keyword in key.lower() or key.lower() in keyword:
                        media_url = url
                        # Detect type by URL extension
                        if url.endswith(".pdf"):
                            media_type = "DOCUMENT"
                            media_filename = f"{key.title().replace(' ', '_')}.pdf"
                        else:
                            media_type = "IMAGE"
                        break
            
            elif tool_name == "search_knowledge":
                # Already have rag_chunks from Node 2; this is a fallback
                extra_chunks = search_knowledge_base(args["query"], state["tenant_id"])
                state["rag_chunks"].extend(extra_chunks)
            
            elif tool_name == "escalate_to_human":
                # BONUS B3: Frustration handover
                state["session_status"] = "NEEDS_HUMAN"
                final_reply = "I understand your concern. Let me connect you with a human agent who can assist you better. Someone will reach out to you shortly."
        
        elif hasattr(part, "text"):
            final_reply = part.text
    
    state["llm_reply"] = final_reply or "I'm here to help! Could you please rephrase your question?"
    state["media_to_send"] = media_url
    state["media_type"] = media_type
    state["media_filename"] = media_filename
    
    return state
```

---

## Node 4: Dispatcher Node

```python
# Purpose: Sends reply to WhatsApp, saves outbound record, updates session
# Typing indicator auto-stops when bot sends message

async def dispatcher_node(state: AgentState) -> AgentState:
    phone_number_id = state["tenant_config"]["whatsapp_phone_number_id"]
    to = state["customer_phone"]
    
    # 1. Send text message (always sent, supports *bold* _italics_)
    await whatsapp_client.send_text_message(
        phone_number_id=phone_number_id,
        to=to,
        text=state["llm_reply"]
    )
    
    # 2. If media, send image or document
    if state["media_to_send"] and state["media_type"] == "IMAGE":
        await whatsapp_client.send_image_message(
            phone_number_id=phone_number_id,
            to=to,
            image_url=state["media_to_send"]
        )
    elif state["media_to_send"] and state["media_type"] == "DOCUMENT":
        await whatsapp_client.send_document_message(
            phone_number_id=phone_number_id,
            to=to,
            doc_url=state["media_to_send"],
            filename=state["media_filename"]
        )
    
    # 3. Save outbound message to MongoDB
    new_status = state["session_status"] if state["session_status"] == "NEEDS_HUMAN" else "RESOLVED"
    
    await db.message_audit_log.insert_one({
        "message_id": str(uuid4()),
        "session_id": state["session_id"],
        "tenant_id": state["tenant_id"],
        "direction": "OUTBOUND",
        "sender": "BOT",
        "text_content": state["llm_reply"],
        "media_url": state["media_to_send"],
        "media_type": state["media_type"],
        "agent_state": "SENT",
        "timestamp": datetime.utcnow()
    })
    
    # 4. Update session status
    await db.chat_sessions.update_one(
        {"session_id": state["session_id"]},
        {"$set": {
            "status": new_status,
            "last_message_at": datetime.utcnow(),
            "$inc": {"message_count": 2}
        }}
    )
    
    state["session_status"] = new_status
    return state
    # NOTE: Typing indicator auto-extinguishes when bot sends a message to WhatsApp
```

---

## Graph Compilation

```python
# app/agent/graph.py

from langgraph.graph import StateGraph, END

def build_graph():
    graph = StateGraph(AgentState)
    
    graph.add_node("acknowledge", acknowledge_node)
    graph.add_node("retrieve_context", context_retriever_node)
    graph.add_node("llm_reason", llm_reasoning_node)
    graph.add_node("dispatch", dispatcher_node)
    
    graph.set_entry_point("acknowledge")
    graph.add_edge("acknowledge", "retrieve_context")
    graph.add_edge("retrieve_context", "llm_reason")
    graph.add_edge("llm_reason", "dispatch")
    graph.add_edge("dispatch", END)
    
    return graph.compile()

agent_graph = build_graph()
```

---

## Graph Diagram

```
[START]
   │
   ▼
┌──────────────┐      ┌──────────────────────────────────────────┐
│  ACKNOWLEDGE │──────► read_receipt + typing_ON + save_to_mongo │
└──────┬───────┘      └──────────────────────────────────────────┘
       │
       ▼
┌──────────────────┐  ┌────────────────────────────────────────────────────┐
│ CONTEXT RETRIEVER│──► tenant_config + last_5_msgs + RAG_chunks + vision  │
└──────┬───────────┘  └────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐      ┌──────────────────────────────────────────────────────┐
│ LLM REASONING│──────► Gemini 2.5 Flash + tools: get_media / escalate_human │
└──────┬───────┘      └──────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐      ┌────────────────────────────────────────────────┐
│  DISPATCHER  │──────► send_text + send_media + save_to_mongo + status │
└──────┬───────┘      └────────────────────────────────────────────────┘
       │
      [END]
```

---

## How LangGraph Runs in Background (FastAPI)

```python
# In webhook POST handler:

@router.post("/api/webhooks/whatsapp")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    
    # VALIDATE SIGNATURE FIRST (bonus B1)
    # ...
    
    # Extract message data
    message_data = extract_message(payload)
    if not message_data:
        return Response(status_code=200)  # always 200 to Meta
    
    # Return 200 IMMEDIATELY — before anything else
    # LangGraph runs in background
    background_tasks.add_task(run_agent, message_data)
    
    return Response(status_code=200)  # Meta gets this in < 100ms


async def run_agent(message_data: dict):
    try:
        initial_state = AgentState(
            tenant_id=message_data["tenant_id"],
            customer_phone=message_data["from"],
            session_id=message_data["session_id"],
            whatsapp_message_id=message_data["message_id"],
            inbound_text=message_data["text"],
            inbound_media_url=message_data.get("media_url"),
            inbound_media_type=message_data.get("media_type"),
            # ... rest initialized to None
        )
        await agent_graph.ainvoke(initial_state)
    except Exception as e:
        # Log error but don't crash — Meta already got 200 OK
        logger.error(f"Agent error: {e}")
```
