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
        "name": "search_catalog",
        "description": (
            "Search the visual product/service catalog and show the customer the single best-matching "
            "item — its photo AND its details (price, colors, material, delivery time) together. "
            "Use this when the customer wants to SEE or find a product by description rather than by exact name, "
            "e.g. 'show me a green leather sofa', 'do you have a marble dining table', "
            "'what beds do you have', 'I need an AC service'. The item's image is sent automatically."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "What the customer is looking for, in their own words.",
                }
            },
            "required": ["description"],
        },
    },
    {
        "name": "search_knowledge",
        "description": (
            "Search the knowledge base for FACTUAL answers about policies, delivery, warranty, "
            "showrooms, payment, or general FAQs (not a specific product photo). "
            "Use for questions like 'what is your return policy', 'how long is delivery', 'where are your showrooms'."
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
