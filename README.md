# RAG Knowledge Base

一个基于 **FastAPI + React + ChromaDB + Redis + LangGraph** 的全栈 RAG 知识库系统。

系统支持用户注册登录、上传 PDF/TXT 文档、文档解析与分块、向量化入库、语义检索、混合检索、rerank 重排序、RAG 问答、Agentic RAG 多轮问答、SSE 流式输出、缓存、调试追踪和离线评估。

---

## 功能概览

### 用户与鉴权

- 用户注册：`POST /users/`
- OAuth2 密码登录：`POST /auth/login`
- JWT 鉴权：受保护接口使用 `Authorization: Bearer <token>`
- 当前用户信息：`GET /users/me`

### 文档管理

- 上传 PDF/TXT 文档：`POST /documents/upload`
- 文档大小限制：默认 10MB
- 后台异步索引：上传后自动解析、分块、embedding、写入向量库
- 文档状态轮询：`GET /documents/{document_id}/status`
- 文档列表：`GET /documents`
- 文本预览：`GET /documents/{document_id}/text`
- 分块预览：`GET /documents/{document_id}/chunks`
- 删除文档：`DELETE /documents/{document_id}`

### 检索能力

- 向量检索：`POST /search/`
- 混合检索：`POST /search/hybrid/`
- 混合检索 + rerank：`POST /search/rerank/`
- 支持 `top_k` 参数控制召回数量
- 支持基于 ChromaDB 的向量持久化
- 支持 BM25 关键词检索与向量检索融合

### RAG 问答

- 标准 RAG 问答：`POST /chat/`
- 标准 RAG 流式输出：`POST /chat/stream`
- 支持检索模式：`vector`、`hybrid`、`rerank`
- 支持精确缓存和语义缓存，减少重复检索与重复 LLM 调用

### Agentic RAG

- Agentic RAG 问答：`POST /chat/agent`
- Agentic RAG SSE 流式输出：`POST /chat/agent/stream`
- 会话列表：`GET /chat/agent/sessions`
- 会话消息：`GET /chat/agent/sessions/{session_id}/messages`

Agent 流程由 LangGraph 编排，当前图结构包括：

```text
classify
  -> cache
  -> rewrite
  -> retrieve_initial
  -> rerank_initial
  -> grade_documents
       -> answer
       -> query_expansion
            -> retrieve_expanded
            -> rerank_expanded
            -> grade_documents
       -> fallback
```

主要能力：

- 问题分类：`chat`、`kb_qa`、`followup`
- 多轮追问改写
- 精确缓存与语义缓存
- 初始检索与 rerank
- 证据质量判断
- Query Expansion / Step-back / HyDE
- 证据不足时 fallback/refuse
- 会话记忆与 trace/debug 信息

---

## 技术栈

### Backend

- Python 3.10
- FastAPI
- SQLAlchemy
- Pydantic / pydantic-settings
- Uvicorn
- SQLite

### RAG / AI

- ChromaDB
- SentenceTransformers
- LangGraph
- LangChain
- OpenAI-compatible LLM API
- BM25 (`rank-bm25`)
- Cross-Encoder rerank
- Redis cache

### Frontend

- React 19
- Vite / rolldown-vite
- Tailwind CSS
- Fetch API

### Infrastructure

- Docker
- Docker Compose
- Redis
- Persistent local storage

---

## 项目结构

```text
rag-knowledge-base
├── app
│   ├── agent                 # LangGraph Agentic RAG 图、节点、工具、状态
│   ├── core                  # 配置
│   ├── middleware            # trace_id、rate limit
│   ├── models                # SQLAlchemy ORM 模型
│   ├── routers               # FastAPI 路由
│   ├── schemas               # Pydantic 请求/响应模型
│   ├── services              # 文档、索引、检索、缓存、LLM、Agent 服务
│   ├── database.py           # SQLite / SQLAlchemy 初始化
│   └── main.py               # FastAPI 应用入口
├── evaluation
│   ├── questions.json
│   ├── questions_multi_gold.json
│   └── multi_gold_knowledge
├── frontend
│   ├── src
│   │   ├── api
│   │   └── pages
│   ├── package.json
│   └── Dockerfile
├── scripts
│   ├── evaluate_agent_day18.py
│   └── evaluate_retrieval.py
├── storage
│   ├── uploads              # 原始上传文件
│   ├── chroma               # ChromaDB 持久化目录
│   └── models               # 本地 embedding/rerank 模型目录
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── rag.db                   # SQLite 数据库
└── README.md
```

---

## 快速启动

### 方式一：Docker Compose

```bash
docker compose up --build
```

启动后访问：

```text
Frontend: http://localhost:5173
Backend API Docs: http://localhost:8000/docs
Health Check: http://localhost:8000/health
```

Docker Compose 会启动：

- `rag-redis`
- `rag-backend`
- `rag-frontend`

并挂载：

- `./storage:/app/storage`
- `./rag.db:/app/rag.db`

### 方式二：本地开发

启动 Redis：

```bash
docker compose up redis
```

启动后端：

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动前端：

```bash
cd frontend
npm install
npm run dev
```

---

## 环境变量

项目使用根目录 `.env`，主要配置项包括：

```env
ENV=dev
SECRET_KEY=dev-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=60

CHUNK_SIZE=500
CHUNK_OVERLAP=100
TOP_K=5
RERANK_CANDIDATES=10
RETRIEVAL_MODE=hybrid
MAX_CHUNKS=500
EMBED_BATCH_SIZE=32

OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

REDIS_URL=redis://127.0.0.1:6379/0
REDIS_TTL_SECONDS=3600

SEMANTIC_CACHE_ENABLED=true
SEMANTIC_CACHE_PERSIST_DIR=storage/chroma
```

注意：

- 本地运行时 Redis 通常使用 `redis://127.0.0.1:6379/0`
- Docker Compose 内部可以使用 Redis 服务名，例如 `redis://redis:6379/0`
- 不要把真实 `OPENAI_API_KEY` 提交到公开仓库

---

## 使用流程

1. 注册账号：`POST /users/`
2. 登录获取 JWT：`POST /auth/login`
3. 上传文档：`POST /documents/upload`
4. 轮询索引状态：`GET /documents/{document_id}/status`
5. 查看文档列表：`GET /documents`
6. 检索测试：`POST /search/hybrid/` 或 `POST /search/rerank/`
7. 发起问答：`POST /chat/` 或 `POST /chat/agent`

---

## 数据存储

### SQLite

默认数据库文件：

```text
rag.db
```

主要表：

- `users`
- `documents`
- `document_jobs`
- `parent_chunks`
- `chat_sessions`
- `chat_messages`

其中 `documents` 表保存上传文件元数据，例如文件名、路径、类型、索引状态。

### 上传文件

```text
storage/uploads
```

### 向量库

```text
storage/chroma
```

默认文档 chunk collection：

```text
document_chunks
```

语义缓存也持久化在 ChromaDB 中，默认 collection 名称为：

```text
semantic_cache
```

---

## 评估脚本

项目包含 RAG 效果评估脚本。

### Agentic RAG 评估

```bash
python scripts/evaluate_agent_day18.py
```

默认读取：

```text
evaluation/questions.json
```

可计算：

- `retrieval_precision_at_k`
- `retrieval_recall_at_k`
- `retrieval_hit_at_k`
- `retrieval_mrr`
- `rerank_precision_at_n`
- `rerank_recall_at_n`
- `rerank_hit_at_n`
- `rerank_mrr`
- `avg_answer_correctness`

使用多 gold chunk 题集：

```bash
EVAL_FILE=evaluation/questions_multi_gold.json python scripts/evaluate_agent_day18.py
```

Windows PowerShell：

```powershell
$env:EVAL_FILE="evaluation/questions_multi_gold.json"
python scripts/evaluate_agent_day18.py
```

### 检索接口评估

```bash
python scripts/evaluate_retrieval.py
```

这个脚本会对比：

- `semantic`
- `hybrid`
- `rerank`

并输出 `Hit@K`。当前脚本需要题集中包含 `expected_keyword` 字段；如果使用现有 `evaluation/questions.json`，需要先适配字段或改为基于 `gold_chunks` 判断。

---

## 常用接口

| Method | Path | 说明 | 鉴权 |
| --- | --- | --- | --- |
| GET | `/ping` | 轻量健康检查 | 否 |
| GET | `/health` | 标准健康检查 | 否 |
| POST | `/users/` | 注册用户 | 否 |
| POST | `/auth/login` | 登录获取 token | 否 |
| GET | `/users/me` | 当前用户信息 | 是 |
| POST | `/documents/upload` | 上传文档并开始索引 | 是 |
| GET | `/documents` | 文档列表 | 是 |
| GET | `/documents/{id}/status` | 文档索引状态 | 是 |
| GET | `/documents/{id}/text` | 文本预览 | 是 |
| GET | `/documents/{id}/chunks` | chunk 预览 | 是 |
| DELETE | `/documents/{id}` | 删除文档 | 是 |
| POST | `/search/` | 向量检索 | 是 |
| POST | `/search/hybrid/` | 混合检索 | 是 |
| POST | `/search/rerank/` | rerank 检索 | 是 |
| POST | `/chat/` | 标准 RAG 问答 | 是 |
| POST | `/chat/stream` | 标准 RAG 流式问答 | 是 |
| POST | `/chat/agent` | Agentic RAG 问答 | 是 |
| POST | `/chat/agent/stream` | Agentic RAG SSE 流式问答 | 是 |
| GET | `/chat/agent/sessions` | Agent 会话列表 | 是 |
| GET | `/chat/agent/sessions/{session_id}/messages` | Agent 会话消息 | 是 |

---

## 前端页面

当前前端包含：

- `Login`：登录
- `Register`：注册
- `Upload`：上传文档
- `Documents`：文档列表与状态
- `Search`：检索测试
- `Chat`：RAG / Agentic RAG 问答

前端默认请求：

```text
http://localhost:8000
```

Docker Compose 中通过：

```env
VITE_API_BASE_URL=http://localhost:8000
```

设置后端地址。

---

## 当前实现亮点

- 完整前后端分离 RAG 知识库系统
- PDF/TXT 上传、解析、分块、索引、删除闭环
- ChromaDB 向量持久化
- BM25 + 向量检索的 hybrid retrieval
- Cross-Encoder rerank
- 分层 chunk 与 parent chunk 存储
- Auto Merge 检索增强
- Query Expansion / Step-back / HyDE
- LangGraph Agentic RAG 编排
- 多轮会话、followup rewrite、session memory
- 精确缓存 + 语义缓存
- 证据不足 fallback/refuse
- SSE 流式输出
- trace_id、请求日志、统一错误处理、限流中间件
- Precision@K / Recall@K / MRR / Hit@K / 答案正确性评估脚本

---

## 注意事项

- 首次运行 SentenceTransformer / rerank 模型时，可能需要下载模型；离线环境建议提前放入 `storage/models`
- 当前数据库默认使用 SQLite，适合本地开发和课程项目演示
- 生产环境建议替换默认 `SECRET_KEY`，并使用更可靠的数据库和密钥管理
- `.env` 中不要保存或提交真实 API Key
- 如果接口返回 429，说明触发了限流，可调整 `RATE_LIMIT_COUNT` 和 `RATE_LIMIT_WINDOW_SECONDS`
