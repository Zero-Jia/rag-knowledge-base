# RAG Knowledge Base Backend

A production-oriented backend service for **Retrieval-Augmented Generation (RAG)**.  
This project focuses on the complete minimal pipeline: **document 鈫?searchable knowledge 鈫?RAG chat API**.

The backend is designed to be **frontend-friendly**, **API-stable**, and **ready for real product integration**.

---

## 馃殌 Features

- User registration & JWT authentication (OAuth2 Password Flow)
- Document upload (PDF / TXT) with asynchronous indexing
- Text parsing, cleaning, and chunking
- Vector embedding & persistent vector store (ChromaDB)
- Semantic search (vector / hybrid / rerank)
- RAG-based chat API (streaming & non-streaming)
- Background indexing tasks & document status lifecycle

---

## 馃 Architecture Overview

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

## 馃洜 Tech Stack

- Python 3.10  
- FastAPI + Uvicorn  
- SQLAlchemy + SQLite  
- JWT + OAuth2 Password Flow + Passlib  
- SentenceTransformers (embeddings)  
- ChromaDB (vector store)  
- PyPDF (PDF parsing)  
- OpenAI SDK (compatible with DeepSeek / OpenAI Chat API)

---

## 馃搨 Project Structure

```
app/
鈹溾攢鈹€ main.py              # Application entry & router registration
鈹溾攢鈹€ core/config.py       # Unified settings from .env
鈹溾攢鈹€ database.py          # Database engine & session
鈹溾攢鈹€ models/              # ORM models (User, Document)
鈹溾攢鈹€ schemas/             # Request / response schemas
鈹溾攢鈹€ routers/             # API routes (auth, users, documents, search, chat)
鈹溾攢鈹€ services/            # RAG core logic
鈹溾攢鈹€ middleware/          # Trace ID, rate limiting, logging
鈹溾攢鈹€ error_handlers.py    # Unified error handling
scripts/                 # Simple test scripts
storage/
鈹溾攢鈹€ uploads/             # Uploaded documents
鈹溾攢鈹€ chroma/              # Vector store
鈹溾攢鈹€ models/              # Cached embedding / rerank models
```

---

## 馃攼 Authentication

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

## 馃攲 API Overview

### Health
- `GET /ping` 鈥?Service health check

### Users & Auth
- `POST /users/` 鈥?Register user
- `POST /auth/login` 鈥?Login and obtain JWT
- `GET /users/me` 鈥?Get current user profile (Auth required)

### Documents
- `POST /documents/upload` 鈥?Upload document & start indexing
- `GET /documents` 鈥?List user documents
- `GET /documents/{id}/status` 鈥?Check indexing status
- `GET /documents/{id}/text` 鈥?Text preview (first N chars)
- `GET /documents/{id}/chunks` 鈥?Chunk preview (debug)

### Search / RAG
- `POST /search/` 鈥?Vector semantic search
- `POST /search/hybrid` 鈥?Hybrid search (vector + keyword)
- `POST /search/rerank` 鈥?Search with rerank model
- `POST /chat/` 鈥?RAG chat (non-streaming)
- `POST /chat/stream` 鈥?RAG chat (streaming text/plain)

馃摌 **Interactive API docs**:  
`http://localhost:8000/docs`

---

## 馃Л Frontend Integration Guide (Quick Start)

### 1锔忊儯 Authentication
```
POST /auth/login  鈫? access_token
Authorization: Bearer <token>
```

### 2锔忊儯 Document Workflow

```
Upload 鈫?Poll Status 鈫?Search / Chat
```

### 3锔忊儯 Search

```json
POST /search/
{
  "query": "浠€涔堟槸娣卞害瀛︿範锛?,
  "top_k": "<TOP_K>"
}
```

### 4锔忊儯 RAG Chat

- Non-streaming: `POST /chat/`
- Streaming: `POST /chat/stream` (text/plain)

---

## ⚙️ Configuration

This project reads runtime configuration from the repository root `.env` via `app/core/config.py`.

1. Copy the template:

```bash
cp .env.example .env
```

2. Edit `.env` values (RAG/retrieval/LLM/Redis) as needed.

3. Restart the backend process so new settings are loaded.

Common keys:
- `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K`, `MAX_CHUNKS`, `EMBED_BATCH_SIZE`
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `TIMEOUT_SECONDS`, `MAX_RETRIES`, `BASE_DELAY`
- `REDIS_URL`, `REDIS_TTL_SECONDS`

See `.env.example` for the full list.
---

## 鈻讹笍 How to Run

```bash
conda create -n rag python=3.10
conda activate rag
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

---

## 馃 API Freeze

API structure is considered **stable**.  
Future changes should be backward compatible or explicitly marked as breaking.

---

## 馃敭 Future Work

- More document formats & batch ingestion
- Retrieval optimization (rerank / recall tuning)
- Permission & access control refinement
- Monitoring & production deployment


