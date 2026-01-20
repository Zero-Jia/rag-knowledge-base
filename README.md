# RAG Knowledge Base Backend

## Introduction

This project is a backend service for a Retrieval-Augmented Generation (RAG) based knowledge base system.
It focuses on a practical foundation that will later connect document ingestion, vector retrieval, and LLMs.
The current implementation delivers a working FastAPI API with user management, authentication, and a local database.

---

## Tech Stack

- Python 3.10
- FastAPI
- Uvicorn
- SQLAlchemy (ORM)
- SQLite (local dev database)
- JWT + OAuth2 password flow
- Passlib (password hashing)

---

## Current Status

- [x] Project skeleton initialized
- [x] FastAPI service running
- [x] Basic health check API (`/ping`)
- [x] Auto-generated API documentation (`/docs`)
- [x] SQLite database wiring and ORM models
- [x] User registration endpoint
- [x] JWT login endpoint
- [x] Protected user profile endpoint

---

## Project Roadmap

- Phase 1: Backend foundation (FastAPI, routing, configuration)
- Phase 2: Document ingestion and preprocessing
- Phase 3: Vector database integration
- Phase 4: RAG pipeline and LLM integration
- Phase 5: API optimization and deployment

---

## API Endpoints

- `GET /ping` Health check
- `POST /users/` Create a user (username, email, password)
- `POST /auth/login` OAuth2 password login, returns JWT
- `GET /users/me` Get current user (requires Bearer token)

Interactive docs are available at `http://localhost:8000/docs`.

---

## Configuration

Environment variables are loaded from `.env` (optional). Defaults are defined in `app/config.py`.

```
APP_NAME=RAG Knowledge Base Backend
DEBUG=true
SECRET_KEY=dev-sectre-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

---

## How to Run

```bash
# create virtual environment
conda create -n rag python=3.10
conda activate rag

# install dependencies
pip install -r requirements.txt

# start server
uvicorn app.main:app --reload --port 8000
```

---

## Basic Usage

```bash
# create a user
curl -X POST http://localhost:8000/users/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"demo\",\"email\":\"demo@example.com\",\"password\":\"pass1234\"}"

# login to get token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo&password=pass1234"

# use token to access protected endpoint
curl http://localhost:8000/users/me \
  -H "Authorization: Bearer <access_token>"
```
