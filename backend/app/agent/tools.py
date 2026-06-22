# Gemini function calling tool definitions

TOOLS = [
    {
        "name": "get_media",
        "description": (
            "Fetch a media file (image or PDF document) from the tenant's media library "
            "when the customer asks to see, receive, or download a catalog, brochure, "
            "price list, product image, showroom photo, invoice, repair diagram, or service menu. "
            "Use this whenever the customer's request implies they want a visual or downloadable asset."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": (
                        "The keyword to look up in the media library. "
                        "Examples: 'catalog', 'sofa', 'showroom', 'price list', "
                        "'invoice', 'repair diagram', 'service menu'"
                    ),
                }
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "search_knowledge",
        "description": (
            "Search the knowledge base for additional detailed information to answer "
            "a customer's question about products, services, pricing, policies, or FAQs. "
            "Use this when you need more specific details not already in your context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant knowledge base articles.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Escalate this conversation to a human agent. Use ONLY when the customer "
            "expresses clear frustration, anger, distress, or dissatisfaction, "
            "or when their request is completely beyond your capability to handle. "
            "Do not use for normal questions even if difficult."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief reason for escalation.",
                }
            },
            "required": ["reason"],
        },
    },
]
