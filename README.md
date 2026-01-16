# RAG Knowledge Base Backend

## Introduction

This project is a backend service for a Retrieval-Augmented Generation (RAG) based knowledge base system.

The goal of this project is to build a practical AI-powered backend that integrates:
- document ingestion
- vector retrieval
- large language models
into a complete, deployable service.

This repository is developed as a winter break engineering project.

---

## Tech Stack

- Python 3.10
- FastAPI
- Uvicorn

---

## Current Status

- [x] Project skeleton initialized
- [x] FastAPI service running
- [x] Basic health check API (`/ping`)
- [x] Auto-generated API documentation (`/docs`)

---

## Project Roadmap

- Phase 1: Backend foundation (FastAPI, routing, configuration)
- Phase 2: Document ingestion and preprocessing
- Phase 3: Vector database integration
- Phase 4: RAG pipeline and LLM integration
- Phase 5: API optimization and deployment

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
