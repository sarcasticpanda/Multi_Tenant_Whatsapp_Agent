# Deployment Plan — Render + Vercel (100% Free)

## Architecture on Cloud

```
Customer (WhatsApp)
       │
Meta Cloud API
       │
       ▼
┌──────────────────────────────────┐
│ Render.com (Free Web Service)    │
│                                  │
│ FastAPI Backend                  │
│ ├── LangGraph Agent              │
│ ├── Chroma DB (in-memory)        │
│ ├── /static/ (PDFs, images)      │
│ └── /api/* (REST endpoints)      │
│                                  │
│ Port: 8000                       │
│ URL:  https://xxx.onrender.com   │
└──────────────────────────────────┘
       │ REST API calls
       ▼
┌──────────────────────────────────┐
│ Vercel (Free)                    │
│ React Dashboard                  │
│ URL: https://xxx.vercel.app      │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│ MongoDB Atlas M0 (Free Cloud)    │
│ Cluster: cluster0.xxx.mongodb.net│
└──────────────────────────────────┘

UptimeRobot (Free) pings /health every 14 min → prevents Render sleep
```

---

## Render Free Tier — Known Issues + Solutions

| Issue | Solution |
|-------|---------|
| Spins down after 15 min | UptimeRobot pings /health endpoint every 14 min |
| Cold start ~30-60s | With UptimeRobot, cold start never happens |
| No persistent disk | Chroma runs in-memory, rebuilt from MongoDB on startup (~15s) |
| 512MB RAM | Chroma in-memory + sentence-transformers fits fine for demo |

---

## Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download sentence-transformers model at build time (not runtime)
# This avoids 30-second download on first request
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy app
COPY . .

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Backend Startup Sequence (app/main.py)

```python
@app.on_event("startup")
async def startup():
    # 1. Connect to MongoDB
    await connect_mongodb()
    
    # 2. Build Chroma index from MongoDB knowledge docs (~15 seconds)
    app.state.chroma_collection = await build_chroma_index()
    
    # 3. Seed tenant data if DB is empty (first run)
    await seed_tenants_if_empty()
    await seed_knowledge_if_empty()
    
    print("Startup complete. Ready to receive webhooks.")

@app.get("/health")
async def health():
    return {"status": "ok"}   # UptimeRobot pings this
```

---

## Environment Variables (Render Dashboard)

```bash
# MongoDB
MONGO_URI=mongodb+srv://user:password@cluster0.xxxxx.mongodb.net/whatsapp_agent?retryWrites=true&w=majority

# Meta WhatsApp
META_PHONE_NUMBER_ID=123456789012345
META_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
META_VERIFY_TOKEN=my_secret_verify_token_123
META_APP_SECRET=abcdef1234567890abcdef1234567890

# Google Gemini (free tier)
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Groq (fallback, free tier)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# App config
APP_BASE_URL=https://your-app-name.onrender.com
```

---

## Step-by-Step Deploy: Backend to Render

```
1. Push code to GitHub

2. Go to render.com → New → Web Service

3. Connect GitHub repo

4. Settings:
   - Name: whatsapp-agent-backend
   - Region: Singapore (closest to India)
   - Branch: main
   - Runtime: Docker
   - Dockerfile Path: ./backend/Dockerfile
   - Instance Type: Free

5. Environment Variables tab → Add all vars from above

6. Deploy → wait ~5 minutes

7. Copy your URL: https://whatsapp-agent-backend.onrender.com
```

---

## Step-by-Step Deploy: Frontend to Vercel

```
1. Go to vercel.com → New Project → Import from GitHub

2. Settings:
   - Framework: Vite
   - Root Directory: frontend
   - Build Command: npm run build
   - Output Directory: dist

3. Environment Variables:
   VITE_API_BASE_URL = https://whatsapp-agent-backend.onrender.com

4. Deploy → URL: https://whatsapp-agent-frontend.vercel.app
```

---

## Meta Webhook Configuration

```
1. Go to Meta Developer Dashboard
2. WhatsApp → Configuration → Edit
3. Callback URL: https://whatsapp-agent-backend.onrender.com/api/webhooks/whatsapp
4. Verify Token: (same as META_VERIFY_TOKEN in your .env)
5. Click Verify and Save
   → Meta calls GET /api/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=...
   → Your server returns hub.challenge
   → Meta shows "Verified" ✓

6. Subscribe to webhook fields:
   - messages ✓
   - message_reactions ✓

7. Test: send WhatsApp message to your test number
   → Should see typing indicator, then bot reply
```

---

## UptimeRobot Setup (Keep Render Awake)

```
1. Go to uptimerobot.com (free account)
2. Add New Monitor:
   - Monitor Type: HTTP(s)
   - Friendly Name: WhatsApp Agent
   - URL: https://whatsapp-agent-backend.onrender.com/health
   - Monitoring Interval: 5 minutes (every 5 min)
3. Save → Render will never sleep
```

---

## docker-compose.yml (Local Development)

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - MONGO_URI=${MONGO_URI}
      - META_PHONE_NUMBER_ID=${META_PHONE_NUMBER_ID}
      - META_ACCESS_TOKEN=${META_ACCESS_TOKEN}
      - META_VERIFY_TOKEN=${META_VERIFY_TOKEN}
      - META_APP_SECRET=${META_APP_SECRET}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GROQ_API_KEY=${GROQ_API_KEY}
      - APP_BASE_URL=http://localhost:8000
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_BASE_URL=http://localhost:8000
    volumes:
      - ./frontend/src:/app/src
    command: npm run dev -- --host
```

---

## Local Dev with ngrok (For Testing Meta Webhook Locally)

```bash
# Install ngrok (free)
# Run your backend locally
uvicorn app.main:app --reload

# In another terminal, expose port 8000
ngrok http 8000

# Copy the https URL: https://xxxx.ngrok-free.app
# Set as webhook URL in Meta Developer Dashboard temporarily
# Test end-to-end locally before deploying
```
