# RAG Knowledge Base System

一个基于 **Retrieval-Augmented Generation (RAG)** 的全栈 AI 知识库系统。

用户可以上传文档（PDF / TXT），系统会自动解析文本、进行分块、向量化并构建向量知识库。用户随后可以通过自然语言提问，系统会检索最相关的文档片段，并结合大语言模型生成答案。

整个系统采用 **FastAPI + React + ChromaDB + Redis + Docker Compose** 构建，实现了一个完整的 **AI 知识库问答系统**。

---

# 项目简介

RAG（Retrieval-Augmented Generation）是一种结合 **信息检索** 与 **大语言模型生成能力** 的技术架构。

传统 LLM 的问题：

* 容易产生 **幻觉（Hallucination）**
* 无法访问 **私有知识库**
* 无法实时更新知识

RAG 的解决方案：

1. 从知识库中 **检索相关内容**
2. 将检索结果作为 **上下文**
3. 再让 LLM 生成答案

本项目实现了一个 **完整的 RAG Pipeline**：

```
用户提问
   ↓
向量检索 (Vector Search)
   ↓
关键词检索 (Keyword Search)
   ↓
Hybrid Retrieval
   ↓
Rerank 重排序
   ↓
LLM 生成回答
```

---

# 系统架构

系统采用 **前后端分离架构**：

```
Frontend (React)
       ↓
FastAPI Backend
       ↓
Retrieval Layer
       ↓
Vector Database (Chroma)
       ↓
Large Language Model
```

系统组件说明：

| 组件                   | 作用     |
| -------------------- | ------ |
| Frontend (React)     | 用户界面   |
| FastAPI Backend      | API 服务 |
| Redis                | 缓存系统   |
| ChromaDB             | 向量数据库  |
| SentenceTransformers | 文本向量化  |
| LLM                  | 生成最终回答 |

---

# 技术栈

## Backend

* Python
* FastAPI
* SQLAlchemy
* Pydantic
* Uvicorn

## AI / RAG

* SentenceTransformers
* Chroma Vector Database
* Hybrid Retrieval
* Rerank Model
* Embedding Batch Processing

## Frontend

* React
* Vite
* Fetch API

## Infrastructure

* Redis
* Docker
* Docker Compose

---

# 核心功能

本项目实现了完整的 **RAG 知识库系统**：

### 用户系统

* 用户注册
* JWT 登录认证
* Token 鉴权访问

### 文档管理

* 上传 PDF / TXT 文档
* 文档解析
* 文本清洗
* 文本分块（Chunking）

### 向量化

* SentenceTransformer Embedding
* 批量 embedding
* 向量持久化

### 检索系统

* 向量检索（Vector Search）
* 关键词检索（Keyword Search）
* Hybrid Retrieval
* Rerank 模型

### Chat 功能

* RAG 问答
* 上下文检索
* Streaming 输出

### 系统优化

* Redis 缓存
* 批量 embedding
* 可配置检索策略
* Docker 容器化部署

---

# 快速启动

## 1 克隆项目

```
git clone https://github.com/yourname/rag-knowledge-base.git
```

进入项目：

```
cd rag-knowledge-base
```

---

## 2 启动系统

```
docker compose up --build
```

Docker 会自动启动：

* backend
* frontend
* redis

---

## 3 访问系统

Backend API 文档：

```
http://localhost:8000/docs
```

Frontend 页面：

```
http://localhost:5173
```

---

# 使用流程

1️⃣ 注册账号

2️⃣ 登录系统

3️⃣ 上传文档

支持：

* PDF
* TXT

4️⃣ 等待文档索引完成

5️⃣ 在 Search 页面提问

系统会：

* 检索相关文档
* 生成回答

---

# 项目结构

```
rag-knowledge-base
│
├── app
│   ├── routers
│   │   ├── auth
│   │   ├── documents
│   │   └── search
│   │
│   ├── services
│   │   ├── embedding
│   │   ├── retrieval
│   │   ├── hybrid_retrieval
│   │   └── rerank
│   │
│   ├── models
│   ├── schemas
│   └── core
│
├── frontend
│   ├── src
│   ├── pages
│   └── components
│
├── storage
│   ├── uploads
│   └── chroma
│
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# 项目亮点

本项目实现了一个 **完整 AI 工程级 RAG 系统**：

* 完整 **RAG Pipeline**
* Hybrid Retrieval（向量 + 关键词）
* Rerank 提升检索质量
* Streaming Chat
* Redis 缓存优化
* 批量 embedding
* 前后端分离
* Docker Compose 一键部署

项目特点：

* 工程结构清晰
* 可扩展性强
* 适合 AI 系统学习与实践

