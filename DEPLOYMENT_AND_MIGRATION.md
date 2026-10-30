# Multi-Source AI Tutor: Secure Authentication, MongoDB Persistence, and Deployment Guide

## 1. System Architecture Overview

The Multi-Source AI Tutor has been upgraded into a multi-tenant, secure learning platform with:

- **Frontend**: Next.js 14 App Router, React 18, TypeScript, TailwindCSS.
  - Proxies `/api/:path*` to the FastAPI backend (`http://localhost:8000/api/:path*`).
  - Supports Secure, HttpOnly cookie sessions (`credentials: 'include'`).
  - Modular components: `ConversationSidebar`, `ChatPanel`, `IngestPanel`, `SourcePanel`, `AnswerCard`, `ProvenanceTag`, `AuthModal`, `ProjectModal`.
- **Backend**: FastAPI, Python 3.11, Pydantic v2, Uvicorn.
  - Shared asynchronous connection pooling with Motor / PyMongo.
  - Lifespan management for startup and graceful connection cleanup.
  - Argon2id password hashing and JWT token issuance.
  - Strict ownership isolation across users, projects, chats, and vector indexes.
- **Database**: MongoDB Atlas (`ai_tutor_dev` / `ai_tutor_prod`).
  - Structured collections: `users`, `projects`, `sources`, `conversations`, `messages`.
  - Database indexes for email uniqueness, project ownership, conversation chronological activity, and message timestamps.
- **Vector Store & Embeddings**: FAISS CPU with local persistence (`data/faiss/`).
  - Replaced unsafe Python pickle metadata (`.meta.pkl`) with safe structured JSON (`.meta.json`).
  - Path traversal protections and stable index sanitization (`uuid`).
- **LLM Synthesis**: Groq API with bounded recent multi-turn conversation context, source conflict classification, and inline citation provenance.

---

## 2. MongoDB Atlas Configuration

### Step 1: Create MongoDB Atlas Cluster
1. Log in to [MongoDB Atlas](https://cloud.mongodb.com/).
2. Create a new cluster (M0 Free Tier or dedicated M10+ for production).
3. Under **Security > Database Access**:
   - Create a database user (e.g. `ai_tutor_app_user`) with read and write permissions to `ai_tutor_dev` (development) or `ai_tutor_prod` (production).
   - Use a strong, URL-encoded password.
4. Under **Security > Network Access**:
   - Add your server/deploy host IP address (or `0.0.0.0/0` with strict credential authentication for development).

### Step 2: Connection String Format
```env
MONGODB_URI=mongodb+srv://<username>:<encoded-password>@<cluster>.mongodb.net/
MONGODB_DATABASE=ai_tutor_dev
```

---

## 3. Environment Variables

Create `.env` in `backend/` based on `backend/.env.example`:

```env
# Application Environment
APP_ENV=development
SECRET_KEY=change-this-to-a-secure-random-32-byte-hex-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# MongoDB Configuration
MONGODB_URI=mongodb+srv://<username>:<encoded-password>@<cluster>.mongodb.net/
MONGODB_DATABASE=ai_tutor_dev

# CORS Settings (comma-separated origins)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Cookie Security
COOKIE_SECURE=false
COOKIE_SAMESITE=lax

# Groq LLM Configuration
GROQ_API_KEY=your_groq_api_key_here
GROQ_PRIMARY_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODEL=llama3-70b-8192

# FAISS Persistence Directory
FAISS_INDEX_DIR=data/faiss
```

> **Security Note**: Never commit real database credentials or secret keys to version control. In production, set `COOKIE_SECURE=true` and configure HTTPS.

---

## 4. FAISS Safe Metadata Migration Guide

### Vulnerability Addressed
Previous versions stored FAISS chunk and source metadata in binary Python pickle format (`{session_id}.meta.pkl`), which poses severe remote code execution risks on deserialization (`pickle.load`).

### Solution Implemented
1. All new metadata files are written in standard, safe structured JSON: `{index_id}.meta.json`.
2. Path traversal attacks are mitigated by sanitizing all index identifiers against directory boundary escapes.
3. Loading helper (`load_index`) automatically inspects the safe JSON file. If a legacy pickle file exists from a local session, it converts it safely into `.meta.json` without unpickling arbitrary foreign files.

### Backup Strategy
Before performing data migrations:
```bash
# Backup existing FAISS indexes and metadata
tar -czvf faiss_backup_$(date +%Y%m%d).tar.gz backend/data/faiss/
```

---

## 5. Local Development & Verification

### Running the Backend
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate   # Windows (or 'source venv/bin/activate' on Linux/macOS)
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Running the Frontend
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### Running Test Suites
Execute the automated test suites from `backend/`:
```bash
# Phase 1: MongoDB connection, client lifecycle & index verification
python test_phase1_db.py

# Phase 2: Registration, Argon2id hashing, login & JWT cookie verification
python test_phase2_auth.py

# Phase 3: Project ownership, safe FAISS indexing & multi-tenant isolation
python test_phase3_projects.py

# Phase 4: Conversations, multi-turn messages, bounded history & archiving
python test_phase4_conversations.py

# End-to-End: Verification through Next.js proxy (http://localhost:3000/api)
python test_e2e_proxy_and_platform.py
```

---

## 6. Production Deployment

### Backend (Docker / Linux VM)
1. Set `APP_ENV=production`, `COOKIE_SECURE=true`, and provide production `SECRET_KEY` and `MONGODB_DATABASE=ai_tutor_prod`.
2. Run with production WSGI/ASGI workers:
   ```bash
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
   ```
3. Use a persistent volume mount for `backend/data/faiss/` to ensure vector store durability.

### Frontend (Vercel / Node.js)
1. Configure `NEXT_PUBLIC_API_URL` or keep the Next.js API rewrites pointing to your production backend domain.
2. Build production assets:
   ```bash
   npm run build
   npm run start
   ```
3. Ensure HTTPS is enforced on both frontend and backend domains to support `Secure` and `SameSite` cookies.
