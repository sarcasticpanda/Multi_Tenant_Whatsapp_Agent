from app.db.mongodb import get_db
from datetime import datetime
from uuid import uuid4

TENANT_A_DOCS = [
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_a", "doc_type": "product",
        "title": "Milano Sofa",
        "content": "The Milano Sofa is crafted from premium Italian leather, available in 8 colors: Ivory, Cognac, Midnight Black, Forest Green, Navy Blue, Blush Pink, Charcoal, and Cream. Dimensions: 220cm W x 90cm D x 85cm H. Price: Rs 1,85,000. Delivery: 4-6 weeks. Features: adjustable headrests, solid walnut frame, 10-year structural warranty.",
        "source": "product_catalog", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_a", "doc_type": "product",
        "title": "Valencia Dining Set",
        "content": "Valencia 8-Seater Dining Set features a Carrara marble top and solid teak base. Table: 240cm x 110cm. Chairs: Italian leather upholstered with armrests. Price: Rs 3,20,000 for full set (table + 8 chairs). Delivery: 6-8 weeks. Customizations available: marble color (Carrara White, Nero Marquina), chair fabric.",
        "source": "product_catalog", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_a", "doc_type": "product",
        "title": "Monaco King Bed Frame",
        "content": "Monaco King Bed Frame in premium upholstered velvet or leather. Size: 180cm x 200cm (king). Headboard: padded with button tufting. Price: Rs 2,10,000. Options: Grey velvet, Ivory leather, Emerald velvet. Includes wooden slats, no mattress. Delivery: 5-7 weeks.",
        "source": "product_catalog", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_a", "doc_type": "product",
        "title": "Riviera Coffee Table",
        "content": "Riviera Coffee Table with tempered glass top and brushed steel frame. Dimensions: 120cm x 60cm x 45cm. Price: Rs 65,000. Available in: Clear glass/silver frame, Smoked glass/gold frame. Delivery: 3-4 weeks. Weight capacity: 50kg.",
        "source": "product_catalog", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_a", "doc_type": "faq",
        "title": "Delivery and Shipping Policy",
        "content": "We deliver across India. Delhi, Mumbai, Bangalore: 4-6 weeks. Other metros (Chennai, Hyderabad, Pune): 6-8 weeks. Tier-2 cities: 8-10 weeks. Free delivery for orders above Rs 1,00,000. Assembly included at no extra cost. All deliveries are tracked and you receive SMS + WhatsApp updates at each stage.",
        "source": "faq", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_a", "doc_type": "faq",
        "title": "Warranty Policy",
        "content": "All furniture comes with 3-year structural warranty and 1-year fabric/leather warranty. Warranty covers manufacturing defects, frame issues, and upholstery stitching defects. Not covered: damages from misuse, water spills, pet scratches, or sunlight fading. For warranty claims: WhatsApp us with your order number and photos within 7 days of noticing the issue.",
        "source": "faq", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_a", "doc_type": "faq",
        "title": "Showroom Locations and Hours",
        "content": "Showrooms: Mumbai - Bandra West, Turner Road (Mon-Sun 10am-8pm). Delhi - Defence Colony, Main Market (Mon-Sun 11am-8pm). Bangalore - Indiranagar, 12th Main (Mon-Sun 10am-8pm). Showrooms are open all days including holidays. Appointments not required but recommended for personalized consultations. Call or WhatsApp to book.",
        "source": "faq", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_a", "doc_type": "pricing",
        "title": "Price Range and EMI Options",
        "content": "Price ranges: Sofas Rs 80,000 to Rs 4,00,000. Dining sets Rs 1,50,000 to Rs 6,00,000. Beds Rs 90,000 to Rs 3,50,000. Coffee tables Rs 30,000 to Rs 1,50,000. EMI available: 0% EMI for 12 months on HDFC and ICICI credit cards for orders above Rs 1,00,000. No-cost EMI also on Amazon Pay and Bajaj Finserv.",
        "source": "pricing", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_a", "doc_type": "faq",
        "title": "Return and Exchange Policy",
        "content": "Returns accepted within 7 days of delivery for manufacturing defects only. Custom orders (non-standard colors or sizes) are non-returnable. Exchange for same value allowed within 30 days. Refund processed within 7-10 business days via original payment method. Items must be in original condition with packaging.",
        "source": "faq", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_a", "doc_type": "faq",
        "title": "Contact and Support",
        "content": "Contact Lumiere Luxury Furniture: Call or WhatsApp +91 98200 12345 (Mon-Sun 10am-8pm). Email: care@lumiere-furniture.in. For order status, design consultations, or bulk/corporate enquiries, ask here on WhatsApp and we'll connect you to a design consultant. You can also visit any of our Mumbai, Delhi, or Bangalore showrooms.",
        "source": "faq", "created_at": datetime.utcnow(),
    },
]

TENANT_B_DOCS = [
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_b", "doc_type": "service",
        "title": "Oil Change Service",
        "content": "Oil change options: Standard mineral oil Rs 1,200 (includes oil filter, 5-point inspection). Semi-synthetic Rs 1,800. Full synthetic Rs 2,500. Diesel engine surcharge Rs 300 extra. Recommended frequency: mineral every 5,000 km, synthetic every 10,000 km. Duration: 45-60 minutes. Free multi-point inspection included.",
        "source": "service_menu", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_b", "doc_type": "service",
        "title": "Brake Service",
        "content": "Brake services: Brake pad replacement Rs 2,500 per axle (pads + labor). Brake rotor/disc replacement Rs 4,500 per rotor. Brake fluid change Rs 800. Full brake overhaul (all 4 wheels, pads + rotors + fluid): Rs 14,000. 6-month or 10,000 km warranty on parts. Duration: 2-3 hours.",
        "source": "service_menu", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_b", "doc_type": "service",
        "title": "AC Service",
        "content": "AC services: Gas recharge (R134a refrigerant) Rs 1,500. AC compressor check Rs 500. Cabin air filter replacement Rs 800. Full AC service (cleaning, recharge, leak check, filter): Rs 3,500. AC compressor replacement (with part): Rs 8,000 to Rs 18,000 depending on car model. 3-month warranty on gas recharge. Duration: 1-2 hours.",
        "source": "service_menu", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_b", "doc_type": "service",
        "title": "Service Packages",
        "content": "Basic Package Rs 2,500: oil change (mineral) + tire rotation + 15-point inspection + free wash. Silver Package Rs 5,500: Basic + brake check + AC gas check + battery test. Gold Package Rs 9,500: Silver + full AC service + coolant flush + spark plug replacement + wheel alignment. All packages include complimentary car wash and 3-month service warranty.",
        "source": "service_menu", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_b", "doc_type": "faq",
        "title": "Appointment Booking",
        "content": "Book appointments via WhatsApp, phone call, or walk-in. Service hours: Monday to Saturday 8am to 7pm, Sunday 9am to 3pm. Walk-in wait time: 1-3 hours. With appointment: service starts within 30 minutes of arrival. We service all major brands: Maruti Suzuki, Hyundai, Tata, Honda, Toyota, Mahindra, KIA, MG, Skoda, Volkswagen. Pickup and drop available in a 10km radius for Rs 299.",
        "source": "faq", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_b", "doc_type": "faq",
        "title": "Warranty on Service",
        "content": "All service work comes with 3-month or 3,000 km warranty (whichever comes first). Parts warranty: 6 months or 10,000 km. If any issue arises within warranty period, we fix it at no charge. Warranty void if car is taken to another service center or unauthorized modifications are made. For warranty claims: show your service invoice.",
        "source": "faq", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_b", "doc_type": "faq",
        "title": "Payment Methods",
        "content": "We accept: Cash, UPI (GPay, PhonePe, Paytm), all debit and credit cards, net banking. EMI available on credit cards above Rs 5,000 service bill. No extra charges for card payments. GST invoice provided for all services. Corporate accounts available for fleet customers (minimum 5 vehicles).",
        "source": "faq", "created_at": datetime.utcnow(),
    },
    {
        "doc_id": str(uuid4()), "tenant_id": "tenant_b", "doc_type": "faq",
        "title": "Contact and Location",
        "content": "Contact AutoCare Services: Call or WhatsApp +91 98765 43210 (Mon-Sat 8am-7pm, Sun 9am-3pm). Email: support@autocare.in. Workshop address: 24 MG Road, near Metro Station. For roadside assistance or emergency towing, call our 24x7 helpline +91 98765 00000. To book a service, just tell us your car model and preferred date here on WhatsApp.",
        "source": "faq", "created_at": datetime.utcnow(),
    },
]


async def seed_knowledge_if_empty() -> None:
    db = get_db()
    count = await db.knowledge_docs.count_documents({})
    if count == 0:
        all_docs = TENANT_A_DOCS + TENANT_B_DOCS
        await db.knowledge_docs.insert_many(all_docs)
        print(f"Seeded {len(all_docs)} knowledge docs ({len(TENANT_A_DOCS)} Tenant A, {len(TENANT_B_DOCS)} Tenant B)")
    else:
        print(f"Knowledge docs already seeded ({count} found)")
