# Day1 - 当前RAG主链路梳理

## 1. 聊天入口
- router 文件：`app/routers/chat.py`
- 接口路径：
  - 非流式：`POST /chat/`
  - 流式：`POST /chat/stream`
- 请求 schema：`ChatRequest`
  - 主要字段：
    - `question`
    - `retrieval_mode`
    - `top_k`
- 调用的 service：
  - 非流式：`chat_with_rag`
  - 流式：`stream_chat_with_rag`

---

## 2. 聊天主流程

### 2.1 非流式聊天主流程
入口函数：`app/services/chat_service.py` 中的 `chat_with_rag`

执行顺序：

1. 接收用户问题 `question`
2. 清洗问题字符串（去空格）
3. 构造 chat cache key
4. 查询精确缓存（Redis）
   - 命中则直接返回
5. 查询语义缓存（semantic cache）
   - 命中则返回，并顺手写入精确缓存
6. 如果缓存都未命中，则进入正常 RAG：
   - 调用 `rag_retrieve(q)` 做检索
   - 调用 `build_messages(q, chunks)` 构造 prompt messages
   - 调用 `generate_answer(messages)` 生成最终答案
7. 将结果写入：
   - 精确缓存
   - 语义缓存
8. 返回 payload：
   - `question`
   - `answer`
   - `chunks`
   - `cache_hit`
   - `cache_type`
   - `semantic_similarity`
   - `matched_cached_question`

### 2.2 流式聊天主流程
入口函数：`app/services/chat_service.py` 中的 `stream_chat_with_rag`

执行顺序：

1. 接收用户问题 `question`
2. 构造 stream cache key
3. 查询精确缓存
   - 命中则按 chunk_size 切片流式返回 answer
4. 查询语义缓存
   - 命中则按 chunk_size 切片流式返回 answer
5. 如果缓存都未命中，则进入正常流式 RAG：
   - `rag_retrieve(q)`
   - `build_messages(q, chunks)`
   - `stream_answer(messages)`
6. 在流式输出完成后，将最终 answer_text 写入：
   - 精确缓存
   - 语义缓存

---

## 3. 检索相关

### 3.1 基础向量检索
文件：`app/services/retrieval_service.py`

核心函数：`retrieve_chunks(query, top_k)`

逻辑：
1. 使用 `EmbeddingService` 对 query 向量化
2. 使用 `VectorStore` 执行向量搜索
3. 从返回结果中取出：
   - `documents`
   - `metadatas`
   - `distances`
4. 组装成 chunks 列表，格式大致为：
   - `text`
   - `document_id`
   - `score`

说明：
- 当前 `score` 保留的是原始 distance，通常越小越相近

### 3.2 Hybrid Search
文件：`app/services/hybrid_retrieval.py`

核心函数：`hybrid_retrieve(query, top_k, user_id, mode)`

逻辑：
1. 先查 search cache
2. 使用 `retrieve_chunks` 做向量召回，拿到更大的候选集
3. 使用 `bm25_rerank` 对候选集整体打分
4. 对向量分数和 BM25 分数分别做归一化
5. 融合得到 `final_score`
   - 当前融合公式：`0.7 * vector + 0.3 * bm25`
6. 按融合分数排序并截断为 top_k
7. 写入 search cache

### 3.3 Rerank
文件：`app/services/rerank_service.py`

核心类：`RerankService`
核心方法：`rerank(query, chunks)`

逻辑：
1. 加载 CrossEncoder 模型
2. 将 `(query, doc_text)` 组成 pairs
3. 对每个 chunk 打 rerank score
4. 将 `rerank_score` 写回 chunk
5. 按 rerank_score 降序排序后返回

---

## 4. LLM 调用相关

文件：`app/services/llm_service.py`

### 4.1 非流式生成
函数：`generate_answer(messages, temperature, max_retries, timeout)`

逻辑：
1. 创建 OpenAI 兼容 client
2. 校验：
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`
   - `OPENAI_MODEL`
3. 调用 `client.chat.completions.create(...)`
4. 获取最终文本结果
5. 支持有限重试 + 指数退避 + 超时控制

### 4.2 流式生成
函数：`stream_answer(messages, temperature, timeout)`

逻辑：
1. 创建 OpenAI 兼容 client
2. 通过 `stream=True` 调用模型
3. 逐 token yield 给上层
4. 若失败，返回错误提示字符串而不是直接崩掉

---

## 5. 当前可复用模块

我认为后续升级 Agent 时可直接复用的模块有：

- `app/services/chat_service.py`
- `app/services/retrieval_service.py`
- `app/services/hybrid_retrieval.py`
- `app/services/rerank_service.py`
- `app/services/llm_service.py`
- `app/services/cache_service.py`
- `app/services/semantic_cache_service.py`
- `app/services/prompt_builder.py`
- `app/services/rag_retrieval.py`

---

## 6. 当前RAG调用链

### 非流式
用户问题
-> `app/routers/chat.py` 中的 `chat_api`
-> `chat_with_rag(question, user_id, retrieval_mode, top_k)`
-> 精确缓存 `get_cache`
-> 语义缓存 `find_semantic_cached_answer`
-> `rag_retrieve(q)` 做检索
-> `build_messages(q, chunks)` 构造 prompt
-> `generate_answer(messages)` 生成答案
-> 写入 exact cache + semantic cache
-> 返回答案

### 流式
用户问题
-> `app/routers/chat.py` 中的 `chat_stream_api`
-> `stream_chat_with_rag(question, user_id, retrieval_mode, top_k)`
-> 精确缓存
-> 语义缓存
-> `rag_retrieve(q)`
-> `build_messages(q, chunks)`
-> `stream_answer(messages)`
-> 写入缓存
-> 流式返回答案

---

## 7. 我对当前项目结构的理解

当前项目其实已经不是一个“最基础版”的 RAG 了，而是一个带有：
- 精确缓存
- 语义缓存
- 向量检索
- Hybrid Search
- Rerank
- 非流式 / 流式输出
的较完整 RAG 系统。

因此后续升级 Agent 时，不需要推倒重来，而是应该：
- 保留原有 services
- 新增 `app/agent/`
- 将旧的 retrieval / cache / rerank / llm 能力封装成 Agent 工具
- 在 chat 主入口逐步切换到 agent graph

---

## 8. 今天遇到的问题
- 目前还没有完全看到 `rag_retrieve` 和 `prompt_builder` 的实现细节
- 还不知道 `retrieval_mode` 在 `rag_retrieve` 内部是否已经动态生效
- 还需要进一步确认：
  - 现有主流程是否已经调用 hybrid search
  - rerank 是否已经在主链路中默认启用