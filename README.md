# RAG Knowledge Base Backend

A production-oriented backend service for **Retrieval-Augmented Generation (RAG)**.  
This project focuses on the complete minimal pipeline: **document → searchable knowledge → RAG chat API**.

The backend is designed to be **frontend-friendly**, **API-stable**, and **ready for real product integration**.

---

## 🚀 Features

- User registration & JWT authentication (OAuth2 Password Flow)
- Document upload (PDF / TXT) with asynchronous indexing
- Text parsing, cleaning, and chunking
- Vector embedding & persistent vector store (ChromaDB)
- Semantic search (vector / hybrid / rerank)
- RAG-based chat API (streaming & non-streaming)
- Background indexing tasks & document status lifecycle

---

## 🧠 Architecture Overview

The project follows a clear layered design:

- **models**  
  Define database tables, fields, and relationships (SQLAlchemy ORM)

- **schemas**  
  Define API request/response contracts (Pydantic models)

- **routers**  
  Define API endpoints and HTTP behavior

- **services**  
  Contain core RAG logic: parsing, chunking, embedding, retrieval, chat

This separation keeps **API design, business logic, and persistence cleanly decoupled**.

---

## 🛠 Tech Stack

- Python 3.10  
- FastAPI + Uvicorn  
- SQLAlchemy + SQLite  
- JWT + OAuth2 Password Flow + Passlib  
- SentenceTransformers (embeddings)  
- ChromaDB (vector store)  
- PyPDF (PDF parsing)  
- OpenAI SDK (compatible with DeepSeek / OpenAI Chat API)

---

## 📂 Project Structure

```
app/
├── main.py              # Application entry & router registration
├── config.py            # Config & environment variables
├── database.py          # Database engine & session
├── models/              # ORM models (User, Document)
├── schemas/             # Request / response schemas
├── routers/             # API routes (auth, users, documents, search, chat)
├── services/            # RAG core logic
├── middleware/          # Trace ID, rate limiting, logging
├── error_handlers.py    # Unified error handling
scripts/                 # Simple test scripts
storage/
├── uploads/             # Uploaded documents
├── chroma/              # Vector store
├── models/              # Cached embedding / rerank models
```

---

## 🔐 Authentication

This backend uses **JWT Bearer authentication**.

### Login Flow
1. `POST /auth/login`
2. Receive `access_token`
3. Add header to all protected requests:

```
Authorization: Bearer <access_token>
```

Swagger UI supports this directly via **Authorize**.

---

## 🔌 API Overview

### Health
- `GET /ping` – Service health check

### Users & Auth
- `POST /users/` – Register user
- `POST /auth/login` – Login and obtain JWT
- `GET /users/me` – Get current user profile (Auth required)

### Documents
- `POST /documents/upload` – Upload document & start indexing
- `GET /documents` – List user documents
- `GET /documents/{id}/status` – Check indexing status
- `GET /documents/{id}/text` – Text preview (first 1000 chars)
- `GET /documents/{id}/chunks` – Chunk preview (debug)

### Search / RAG
- `POST /search/` – Vector semantic search
- `POST /search/hybrid` – Hybrid search (vector + keyword)
- `POST /search/rerank` – Search with rerank model
- `POST /chat/` – RAG chat (non-streaming)
- `POST /chat/stream` – RAG chat (streaming text/plain)

📘 **Interactive API docs**:  
`http://localhost:8000/docs`

---

## 🧭 Frontend Integration Guide (Quick Start)

### 1️⃣ Authentication
```
POST /auth/login  →  access_token
Authorization: Bearer <token>
```

### 2️⃣ Document Workflow

```
Upload → Poll Status → Search / Chat
```

### 3️⃣ Search

```json
POST /search/
{
  "query": "什么是深度学习？",
  "top_k": 5
}
```

### 4️⃣ RAG Chat

- Non-streaming: `POST /chat/`
- Streaming: `POST /chat/stream` (text/plain)

---

## ⚙️ Configuration

```env
APP_NAME=RAG Knowledge Base Backend
DEBUG=true

SECRET_KEY=dev-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

---

## ▶️ How to Run

```bash
conda create -n rag python=3.10
conda activate rag
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

---

## 🧊 API Freeze

API structure is considered **stable**.  
Future changes should be backward compatible or explicitly marked as breaking.

---

## 🔮 Future Work

- More document formats & batch ingestion
- Retrieval optimization (rerank / recall tuning)
- Permission & access control refinement
- Monitoring & production deployment
