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

Agent 流程由 LangGraph 编排，采用 **quick path + ReAct 双轨并存** 架构，三层漏斗自动路由：

```text
classify（规则脚本 + LLM JSON 输出 route/need_react）
  -> cache
       -> [前置升级：need_react] react_agent ─┐
       -> rewrite                            │
       -> retrieve_initial                   │
       -> rerank_initial                     │
       -> grade_documents                    │
            -> [后置升级1：证据不足且未升级] ─┤
            -> answer -> grounding_check     │
                 -> [后置升级2：grounding 失败且未升级] ─┤
                 -> END                      │
            -> query_expansion               │
                 -> retrieve_expanded        │
                 -> rerank_expanded          │
                 -> grade_documents          │
            -> fallback                      │
                                             ▼
                         react_agent（create_react_agent 子图）
                         自主拆问 / 多轮 4 工具 / 换词 / 多跳收集证据
                         → 复用 quick path 统一合成答案
                         -> grounding_check -> (fallback | END)
```

主要能力：

- 三层漏斗自动路由（规则脚本硬信号 + LLM 意图识别 + 运行时证据驱动）
- ReAct Agent：`create_react_agent` 子图 + 4 个检索工具（hybrid/vector/keyword/rerank）+ `react_attempted` 防环护栏 + 总开关 `REACT_AGENT_ENABLED`
- Quick Path：多轮追问改写、精确缓存与语义缓存、初始检索与 rerank、证据质量判断、Query Expansion / Step-back / HyDE、证据不足时 fallback/refuse
- Grounding Check：LLM 校验答案是否被证据支持，不通过走 fallback
- 会话记忆、token 统计、trace/debug 信息、SSE 流式 `deep_research` 过渡事件

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
├── .vscode/
│   └── settings.json                        # VS Code 工作区设置
├── app/                                      # ===== 后端主应用 =====
│   ├── agent/                                # LangGraph Agentic RAG 图、节点、工具、状态
│   │   ├── nodes/                            # Agent 图中的各个节点（quick path 静态编排）
│   │   │   ├── __init__.py
│   │   │   ├── answer_node.py                # 答案生成节点，调用 LLM 合成答案并输出 [N] 引用
│   │   │   ├── cache_node.py                 # 缓存查询节点（精确缓存 + 语义缓存）
│   │   │   ├── classify_node.py              # 问题分类节点（规则脚本 + LLM JSON：route / need_react）
│   │   │   ├── fallback_node.py              # 兜底拒答节点（证据不足 / grounding 失败 / ReAct 失败）
│   │   │   ├── grade_documents_node.py      # 证据质量评分节点（LLM 判断片段是否支持问题）
│   │   │   ├── grounding_check_node.py       # Grounding Check 节点（LLM 校验答案是否被证据支持）
│   │   │   ├── query_expansion_node.py       # Query Expansion 节点（Step-back / HyDE / 多子问题）
│   │   │   ├── rerank_expanded_node.py       # expansion 二轮 rerank 节点
│   │   │   ├── rerank_node.py                # 初始 rerank 节点
│   │   │   ├── retrieve_expanded_node.py     # expansion 二轮检索节点
│   │   │   ├── retrieve_node.py              # 初始检索节点（向量 / 混合）
│   │   │   └── rewrite_node.py               # 多轮追问改写节点
│   │   ├── tools/                            # P1-1 检索能力 Tool 化（双轨并存）
│   │   │   ├── __init__.py                   # re-export + build_retrieval_tools() 工厂
│   │   │   ├── _common.py                    # Tool 版共用输出层：format_chunks_for_llm()、pick_score()
│   │   │   ├── cache_tool.py                 # Agent 图内缓存读写辅助函数（非 StructuredTool）
│   │   │   ├── hybrid_tool.py                # hybrid_search 纯函数 + StructuredTool 工厂
│   │   │   ├── keyword_tool.py               # keyword_search（BM25）纯函数 + StructuredTool 工厂
│   │   │   ├── rerank_tool.py                # rerank 纯函数 + StructuredTool 工厂
│   │   │   └── vector_tool.py                # vector_search 纯函数 + StructuredTool 工厂
│   │   ├── __init__.py
│   │   ├── debug.py                          # 图执行期间的调试摘要构建 / 日志格式化
│   │   ├── graph.py                          # LangGraph StateGraph 主图（quick path + ReAct 升级边、三层漏斗路由）
│   │   ├── prompts.py                        # 所有 System Prompt（classify / rewrite / REACT 等）
│   │   ├── react_agent.py                    # P1-2 新增：ReAct Agent 节点（create_react_agent 子图，4 工具收集证据后复用统一合成）
│   │   ├── routing.py                        # P1-2 新增：detect_complex_query() 规则脚本（问号≥2 / 比较词 / 并列分句）
│   │   └── state.py                          # AgentState 定义（含 need_react / react_attempted / react_reason 等扩展字段）
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py                         # pydantic-settings 配置（模型、检索、ReAct、Langfuse 等全部开关）
│   ├── middleware/
│   │   ├── rate_limit.py                     # 限流中间件
│   │   └── trace.py                          # 请求级 trace_id 中间件
│   ├── models/
│   │   ├── __init__.py
│   │   ├── chat_session.py                   # ChatSession / ChatMessage ORM（会话、消息、rag_trace JSON 列）
│   │   ├── document.py                       # Document ORM
│   │   ├── document_job.py                   # DocumentJob ORM（文档索引任务，阶段化进度跟踪）
│   │   ├── parent_chunk.py                   # ParentChunk ORM（分层 chunk：L1 父 / L2 子 / L3 叶子）
│   │   └── user.py                           # User ORM
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py                           # /auth/login 登录
│   │   ├── chat.py                           # /chat/*（标准 RAG / Agentic RAG 问答、SSE、会话管理、token 用量）
│   │   ├── documents.py                      # /documents/*（上传、列表、状态、分块预览、删除）
│   │   ├── health.py                         # /ping /health 健康检查
│   │   ├── search.py                         # /search/ 纯向量检索接口
│   │   ├── search_hybrid.py                  # /search/hybrid/ 混合检索接口
│   │   ├── search_rerank.py                  # /search/rerank/ 混合 + rerank 检索接口
│   │   └── users.py                          # /users/* 注册 / 当前用户
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── agent_chat.py                     # Agent 问答请求/响应 Pydantic 模型
│   │   ├── chat.py                           # 标准 RAG 问答请求/响应 Pydantic 模型
│   │   ├── common.py                         # 通用响应包装模型
│   │   ├── query.py                          # 检索请求 Pydantic 模型
│   │   ├── rag_trace.py                      # rag_trace schema + record_token_usage / record_timing / set_fallback_reason
│   │   └── user.py                           # 用户相关 Pydantic 模型
│   ├── services/                             # ===== 核心业务服务 =====
│   │   ├── __init__.py
│   │   ├── advanced_retrieval.py             # 带 rerank 的检索封装（retrieve_with_rerank）
│   │   ├── agent_chat_service.py             # Agentic RAG 非流式入口（graph.invoke + save_turn）
│   │   ├── agent_memory_service.py           # Agent 会话记忆读/写/清空（re-export chat_session_service）
│   │   ├── agent_stream_service.py           # Agentic RAG SSE 流式入口（graph.stream + deep_research 过渡事件）
│   │   ├── auto_merge_service.py             # Small-to-Big Auto Merge 检索增强（L3→L2→L1 向上归并）
│   │   ├── cache_service.py                  # 精确缓存（Redis）辅助工具
│   │   ├── chat_service.py                   # 标准 RAG 非流式 + 流式入口（vector/hybrid/rerank 三种模式）
│   │   ├── chat_session_service.py           # ChatSession / ChatMessage CRUD + session token 用量聚合
│   │   ├── document_delete_service.py        # 文档完整删除（DB + 向量库 + 关联 chunk + parent_chunk）
│   │   ├── document_job_service.py            # 文档索引任务管理（阶段化：parse→embed→index，进度追踪）
│   │   ├── document_parser.py                # PDF / TXT 解析
│   │   ├── document_service.py               # 文档 CRUD 辅助（DB 层面）
│   │   ├── embedding_service.py              # SentenceTransformer embedding 封装（批处理 + GPU 自动检测）
│   │   ├── hybrid_retrieval.py               # 混合检索（向量 + BM25 融合），对外暴露 keyword_recall 公共入口
│   │   ├── indexing_service.py               # 文档索引全流程编排（parse → chunk → embed → write）
│   │   ├── keyword_search.py                 # BM25 关键词检索底层实现
│   │   ├── langfuse_service.py               # Langfuse v4 SDK 封装（渐进式开关，默认关闭）
│   │   ├── llm_service.py                    # ChatOpenAI 封装 + generate_answer / generate_answer_with_usage
│   │   ├── prompt_builder.py                 # 答案合成 prompt 构建（context 编号 [idx]\n{text} + 引用格式指令）
│   │   ├── query_expansion_service.py        # Step-back / HyDE / 多子问题 Query Expansion
│   │   ├── rag_retrieval.py                  # RAG 检索便捷入口（内部委托 retrieval / hybrid_retrieval）
│   │   ├── request_context.py                # 请求级 request_id（让一次 /chat 的日志能串起来）
│   │   ├── rerank_service.py                 # Cross-Encoder rerank 封装
│   │   ├── retrieval_service.py              # ChromaDB 向量检索底层封装（含 user_id where 过滤）
│   │   ├── search_service.py                 # 旧版 search_chunks 封装（保留兼容）
│   │   ├── semantic_cache_service.py         # 语义缓存（ChromaDB 存储 + 向量相似度匹配）
│   │   ├── text_processing.py                # 文本清洗 + 分块（普通单层 + 分层 HierarchicalChunkSet）
│   │   └── vector_store.py                   # ChromaDB 初始化 + collection 获取 + update_metadatas
│   ├── database.py                           # SQLAlchemy engine / SessionLocal / Base 初始化
│   ├── error_handlers.py                     # FastAPI 全局异常处理器（AppError → HTTP 响应）
│   ├── exceptions.py                         # AppError 自定义异常基类
│   ├── logging_config.py                     # logging 配置（彩色输出 + 结构化）
│   ├── main.py                               # FastAPI 应用入口（app = FastAPI(...) + 路由注册 + startup 事件）
│   └── security.py                           # JWT 签发 / 校验 + 密码 hash + OAuth2PasswordBearer 依赖
├── docs/                                      # 项目文档（开发 Agent 必读）
│   ├── README.md                             # docs 目录索引
│   ├── 00-overview.md                        # 项目总览与架构图
│   ├── 01-gap-analysis.md                    # 与目标架构的差距分析
│   ├── 02-roadmap.md                         # 开发路线图
│   ├── 03-task-backlog.md                    # 任务清单（状态 + 实际改动文件）
│   ├── 04-progress-log.md                    # 开发进度日志（每 session 顶部追加）
│   ├── 05-agent-handoff.md                   # Agent 交接说明（当前状态 + 下一步 + 不可破坏项）
│   └── 06-conventions.md                     # 开发规范（编码、测试、Git）
├── evaluation/
│   ├── questions.json                        # 20 条评估题集（evaluate_agent_day18.py 默认读取）
│   ├── questions_multi_gold.json             # 多 gold chunk 评估题集
│   └── multi_gold_knowledge/                  # 评估用知识源（3 份 .txt）
│       ├── 01_agentic_rag_retrieval_pipeline.txt
│       ├── 02_rag_cache_fallback_design.txt
│       └── 03_rag_evaluation_metrics.txt
├── frontend/                                 # ===== React 前端 =====
│   ├── src/
│   │   ├── api/                              # API 层（fetch 封装）
│   │   │   ├── auth.js                       # /auth/* 接口
│   │   │   ├── chat.js                       # /chat/* 接口（含 agent session token 用量）
│   │   │   ├── client.js                     # fetch 基础封装（base URL + Authorization 拦截器）
│   │   │   ├── documents.js                  # /documents/* 接口
│   │   │   ├── search.js                     # /search/* 接口
│   │   │   └── users.js                      # /users/* 接口
│   │   ├── pages/                            # 页面组件
│   │   │   ├── Chat.jsx                      # 主问答页面（RAG + Agentic RAG + TracePanel + 👍👎）
│   │   │   ├── Documents.jsx                 # 文档列表页面
│   │   │   ├── Login.jsx                     # 登录页面
│   │   │   ├── Register.jsx                  # 注册页面
│   │   │   ├── Search.jsx                    # 检索测试页面
│   │   │   └── Upload.jsx                    # 文档上传页面
│   │   ├── App.css
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── Dockerfile
│   ├── eslint.config.js
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── vite.config.js
├── notes/
│   └── day1_rag_flow.md                      # 早期 RAG 流程笔记
├── scripts/
│   ├── __init__.py
│   ├── evaluate_agent_day18.py               # Agentic RAG 端到端评估脚本（20 case，retrieval / rerank / answer 三维指标）
│   ├── evaluate_retrieval.py                 # 纯检索接口评估脚本（semantic / hybrid / rerank 对比 Hit@K）
│   └── reindex_user_metadata.py              # 回填已有 chunk 的 user_id metadata 脚本
├── storage/                                  # ===== 持久化目录（gitignore） =====
│   ├── uploads/                              # 原始上传文件（PDF / TXT）
│   ├── chroma/                               # ChromaDB 持久化目录（document_chunks + semantic_cache）
│   └── models/                               # 本地 SentenceTransformer / rerank 模型缓存目录
├── .dockerignore
├── .gitignore
├── Dockerfile                                # 后端 Docker 镜像（基于 python:3.10-slim）
├── docker-compose.yml                        # 本地 Docker Compose（redis + backend + frontend）
├── README.md                                 # 本文件
├── requirements.txt                          # Python 依赖（含 langgraph-prebuilt / sentence-transformers / chromadb / langfuse 等）
└── rag.db                                    # SQLite 数据库（users / documents / document_jobs / parent_chunks / chat_sessions / chat_messages）
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

# 检索参数
CHUNK_SIZE=500
CHUNK_OVERLAP=100
TOP_K=5
RERANK_CANDIDATES=10
RETRIEVAL_MODE=hybrid
MAX_CHUNKS=500
EMBED_BATCH_SIZE=32

# LLM（OpenAI 兼容）
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

# ReAct Agent 总开关（默认 False，关闭时 ReAct 零调用、升级边全部回退到 quick path）
REACT_AGENT_ENABLED=false
REACT_RECURSION_LIMIT=25
REACT_TOOL_TEXT_LIMIT=800

# Redis 缓存
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_TTL_SECONDS=3600

# 精确缓存 + 语义缓存
SEMANTIC_CACHE_ENABLED=true
SEMANTIC_CACHE_PERSIST_DIR=storage/chroma

# Langfuse 可观测性（渐进式开关，默认关闭）
LANGFUSE_ENABLED=false
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

注意：

- 本地运行时 Redis 通常使用 `redis://127.0.0.1:6379/0`
- Docker Compose 内部可以使用 Redis 服务名，例如 `redis://redis:6379/0`
- 不要把真实 `OPENAI_API_KEY` 提交到公开仓库
- `REACT_AGENT_ENABLED=false` 时 Agent 图逐字节走 quick path，不影响现有评估结果

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
| GET | `/chat/agent/sessions/{session_id}/usage` | Agent 会话 token 用量（P0-6 新增） | 是 |

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
- ChromaDB 向量持久化 + 分层 chunk 存储 + Small-to-Big Auto Merge
- BM25 + 向量检索的 hybrid retrieval + Cross-Encoder rerank
- LangGraph Agentic RAG 编排，quick path + ReAct 双轨并存
- **ReAct Agent 三层漏斗自动路由**：规则脚本硬信号 + LLM 意图识别 + 运行时证据驱动后置升级
- Query Expansion / Step-back / HyDE 多策略检索增强
- Grounding Check（LLM 校验答案是否被证据支持）+ 证据不足 fallback/refuse
- 精确缓存 + 语义缓存
- 多轮会话、followup rewrite、session memory、chat_messages 持久化（rag_trace JSON 列）
- `[1][2]` inline citation + citations 字段（index / chunk_id / text / score）
- Token 统计（rag_trace.token_usage by_node + total）+ Langfuse 可观测性（可选）
- SSE 流式输出（rag_step / deep_research / content / trace / done）
- JWT 鉴权、user_id 租户隔离、请求级 trace_id、限流、统一错误处理
- Precision@K / Recall@K / MRR / Hit@K / 答案正确性评估脚本（Agent 端到端 + 纯检索对比）

---

## 注意事项

- 首次运行 SentenceTransformer / rerank 模型时，可能需要下载模型；离线环境建议提前放入 `storage/models`
- 当前数据库默认使用 SQLite，适合本地开发和课程项目演示
- 生产环境建议替换默认 `SECRET_KEY`，并使用更可靠的数据库和密钥管理
- `.env` 中不要保存或提交真实 API Key
- 如果接口返回 429，说明触发了限流，可调整 `RATE_LIMIT_COUNT` 和 `RATE_LIMIT_WINDOW_SECONDS`
