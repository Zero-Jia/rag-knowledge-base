# RAG Knowledge Base Backend

**项目简介**
这是一个面向 RAG（Retrieval-Augmented Generation）的知识库后端服务，聚焦在“从文档到可检索知识”的完整最小闭环。当前已实现用户认证、文档上传、解析分块、向量化、向量检索，以及基于检索结果的 RAG 问答接口。
models 定义的是：数据库里“有什么表、有什么字段、表和表怎么关联” 
schemas 定义的是：接口“允许接收什么 / 返回什么” 
routers 定义的是：“当客户端请求某个 URL 时，系统该做什么” 

**核心能力**
- 用户注册与 JWT 登录鉴权
- 文档上传（TXT/PDF）与解析
- 文本清洗与分块
- 向量化与持久化向量库（Chroma）
- 语义检索与 RAG 对话
- 后台索引任务与文档状态机

**技术栈**
- Python 3.10
- FastAPI + Uvicorn
- SQLAlchemy + SQLite
- JWT + OAuth2 Password Flow + Passlib
- SentenceTransformers（向量化）
- ChromaDB（向量检索）
- PyPDF（PDF 解析）
- OpenAI SDK（兼容 DeepSeek/OpenAI 的 Chat API）

**项目结构**
- `app/main.py` 启动入口与路由注册
- `app/config.py` 配置与环境变量
- `app/database.py` 数据库连接与 Session 管理
- `app/models/` ORM 数据模型（User, Document）
- `app/schemas/` Pydantic 请求/响应校验模型
- `app/routers/` API 路由（auth/users/documents/search/chat）
- `app/services/` RAG 核心服务（解析、分块、向量化、检索、对话）
- `scripts/` 简单测试脚本
- `storage/` 运行期数据（上传文件、向量库、模型缓存）

**技能与运用方式**
- API 设计与分层：使用 FastAPI 路由层 + Services 业务层，清晰分离接口与逻辑，便于扩展与测试。
- ORM 建模：用 SQLAlchemy 定义 `User`、`Document` 等表结构，并通过 `Session` 管理事务。
- 认证与安全：JWT + OAuth2 Password Flow 完成登录鉴权，Passlib 对密码进行 bcrypt 哈希。
- 文档处理：基于 `pypdf` 解析 PDF，统一文本清洗，再进行固定长度分块和 overlap。
- 向量化与检索：SentenceTransformers 生成向量，ChromaDB 持久化并支持相似度检索。
- RAG 链路：检索相关 chunks，构造 Prompt，调用 LLM 生成回答。
- 后台任务：文档上传后异步触发索引流程，更新 `Document.status`（pending/processing/done/failed）。

**API 概览**
- `GET /ping` 健康检查
- `POST /users/` 注册用户
- `POST /auth/login` 登录获取 JWT
- `GET /users/me` 获取当前用户信息（需 Bearer Token）
- `POST /documents/upload` 上传文档并触发后台索引
- `GET /documents/{id}/status` 查询文档索引状态
- `GET /documents/{id}/text` 获取文档解析文本预览
- `GET /documents/{id}/chunks` 获取文档分块预览
- `POST /search/` 语义检索
- `POST /chat/` 基于检索结果的 RAG 对话

交互式文档：`http://localhost:8000/docs`

**配置说明**
默认从环境变量读取，未设置则使用代码默认值。

```
APP_NAME=RAG Knowledge Base Backend
DEBUG=true
SECRET_KEY=dev-sectre-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# LLM 相关
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

**如何运行**
```
# 创建虚拟环境
conda create -n rag python=3.10
conda activate rag

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn app.main:app --reload --port 8000
```

**如何操作（最小闭环）**
1. 注册用户
```
curl -X POST http://localhost:8000/users/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"demo\",\"email\":\"demo@example.com\",\"password\":\"pass1234\"}"
```

2. 登录获取 Token
```
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo&password=pass1234"
```

3. 上传文档并触发索引
```
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@./your_doc.pdf"
```

4. 查询索引状态
```
curl http://localhost:8000/documents/<document_id>/status \
  -H "Authorization: Bearer <access_token>"
```

5. 语义检索
```
curl -X POST http://localhost:8000/search/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"你的问题\",\"top_k\":5}"
```

6. RAG 对话
```
curl -X POST http://localhost:8000/chat/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"你的问题\",\"top_k\":5}"
```

**运行说明**
- 模型缓存默认在 `storage/models/`，向量库在 `storage/chroma/`，上传文件在 `storage/uploads/`。
- 如果未配置 `OPENAI_*` 环境变量，`/chat` 会返回 LLM 配置缺失错误。

**后续计划**
- 接入更多文件格式与批量导入
- 向量检索优化（重排、召回策略）
- 文档/用户权限隔离的细化
- API 监控与部署
