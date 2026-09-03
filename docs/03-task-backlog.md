# 任务清单

> **状态约定**：`todo` / `doing` / `done` / `blocked`
> 完成任务请填"实际改动文件"列，便于回溯。

---

## P0 阶段

| 编号 | 任务 | 状态 | 实际改动文件 | 备注 |
|---|---|---|---|---|
| P0-1 | answer_node 输出 inline citation `[1][2]` 映射 chunk_id | done | `state.py`、`nodes/answer_node.py`、`nodes/cache_node.py`、`services/prompt_builder.py`、`services/retrieval_service.py`、`services/hybrid_retrieval.py`、`services/agent_chat_service.py`、`services/agent_stream_service.py` | 引用指令加在 prompt_builder.py（答案 prompt 实际组装处）；citations.source 暂为 document_id，文档名待 P0-4 metadata 补充 |
| P0-2 | groundedness 校验：答案生成后 LLM 判断是否被证据支持，不通过则 fallback | done | `agent/state.py`、`agent/prompts.py`、`agent/nodes/grounding_check_node.py`（新增）、`agent/nodes/fallback_node.py`、`agent/graph.py`、`agent/debug.py`、`services/agent_stream_service.py`、`services/agent_chat_service.py` | 新增 grounding_check 节点，answer→grounding_check→(fallback\|END)；LLM/解析故障保守放行；评估 20/20 grounding passed 无误杀，correctness 0.9 持平基线 |
| P0-3 | retrieve_node / vector_tool / hybrid_tool 加 `tenant_id`/`user_id` metadata filter | done | `services/retrieval_service.py`、`services/hybrid_retrieval.py`、`agent/tools/vector_tool.py`、`agent/nodes/retrieve_node.py` | 检索层 user_id 透传 + ChromaDB where 过滤；user_id None 兼容旧数据；升 cache v5→v6 失效旧缓存；评估 user_id=1 correctness 0.9 持平基线 |
| P0-4 | 文档上传时写入 `tenant_id`/`owner_id` metadata | done | `services/indexing_service.py`、`services/vector_store.py`（新增 `update_metadatas`）、`scripts/reindex_user_metadata.py`（新增） | hierarchy 路径 `_base_metadata` 已写 user_id；non-hierarchy 路径补 user_id；reindex 脚本回填 169 chunks；`Document` model 已有 user_id 无需改 |
| P0-5 | 接入 Langfuse，把 rag_trace 标准化导出 | done | `requirements.txt`、`app/core/config.py`、`app/services/langfuse_service.py`（新增）、`app/services/agent_chat_service.py`、`app/services/agent_stream_service.py` | 选 Langfuse Cloud Hobby 而非本地自建（自建需常驻 ClickHouse+PG+Redis 共 6-8GB，本地开发机不适合）；渐进式开关 `LANGFUSE_ENABLED=False` 默认关闭，开关关闭时零 SDK 初始化/零网络调用；上报顶层 Trace（input=question/output=final_answer/metadata=route+cache+grounding+timing），不上报原文 chunk 全文为 PII 脱敏预留；评估回归 20/20 通过，correctness 0.9/rerank_recall 0.8/retrieval_recall 0.9 全持平基线 |
| P0-6 | token 消耗统计：rag_trace.token_usage 记录各节点/总轮 token | done | `app/core/config.py`、`app/schemas/rag_trace.py`、`app/services/llm_service.py`、`app/agent/nodes/classify_node.py`、`app/agent/nodes/rewrite_node.py`、`app/agent/nodes/answer_node.py`、`app/agent/nodes/grounding_check_node.py`、`app/services/query_expansion_service.py`、`app/agent/debug.py`、`app/services/chat_session_service.py`、`app/services/agent_memory_service.py`、`app/routers/chat.py`、`frontend/src/api/chat.js`、`frontend/src/pages/Chat.jsx` | 按 user 要求只统计 token 不算成本（cost_usd 移除）；放 rag_trace 而非 state 顶层（自动随 save_turn 持久化 + 前端 TracePanel 直读，零 DB schema 变更）；新增 `generate_answer_with_usage` 返回 usage；5 个 LLM 节点写 by_node+total；新增 `GET /chat/agent/sessions/{id}/usage` session 级聚合；前端 TracePanel 加 Token usage + Session total 区块；评估 20/20 correctness 0.9/recall 0.9/rerank 0.8 持平基线 |

### P0-1 详细设计

**目标**：让 answer_node 输出带 `[1][2]` 引用的答案，并在 state 中维护 `citations` 字段。

**state.py 新增字段**：
```python
citations: List[Dict[str, Any]]  # [{index: 1, chunk_id: "...", text: "...", source: "...", score: 0.9}]
```

**prompts.py 调整**：要求 LLM 在引用证据时输出 `[1]` `[2]` 标记，标记序号对应 reranked_docs 顺序。

**answer_node.py 改造**：
1. 调用 LLM 后解析答案中的 `[N]` 标记
2. 从 `reranked_docs` 按 N 映射回 chunk_id、原文、来源文档名
3. 写入 `state["citations"]`

**验收标准**：
1. 答案文本中出现 `[1]` 等标记
2. state 返回 `citations` 字段，含 chunk_id、原文片段、来源文档名
3. 流式输出场景下 citations 在最后一条 SSE 事件返回

### P0-2 详细设计

**目标**：答案生成后做一次 faithfulness 校验，不通过则走 fallback。

**实现方式**：
- 新增 `grounding_check_node`（或在 answer_node 内部增加步骤）
- 用 LLM 判断：`answer` 中的每个 claim 是否被 `reranked_docs` 支持
- 不通过 → 设置 `need_fallback=True`，路由到 `fallback_node`
- graph 增加 edge：`answer → grounding_check → (fallback | END)`

### P0-3 详细设计

**目标**：检索时按 user_id/tenant_id 过滤，保证数据隔离。

**改动点**：
- `vector_tool.py`、`hybrid_tool.py`：查询时加 `where={"user_id": user_id}`
- `retrieve_node.py`：从 state 中拿到 user_id（由 chat 入口注入）
- `routers/chat.py`、`agent_chat_service.py`：把当前用户 id 注入 state
- ChromaDB metadata filter 语法确认

---

## P1 阶段

| 编号 | 任务 | 状态 | 实际改动文件 | 备注 |
|---|---|---|---|---|
| P1-1 | 把 retrieve/rerank/keyword/search 改造成 LangGraph Tool | todo | — | 重构 `app/agent/tools/` |
| P1-2 | 引入 ReAct Agent，保留现有图为 quick path | todo | — | 新增 `react_agent.py` |
| P1-3 | grade 分数 / fallback 率 / 延迟持久化到 DB | todo | — | 新增 `models/metric.py` |
| P1-4 | 监控大盘 API（聚合指标查询） | todo | — | 新增 `routers/metrics.py` |
| P1-5 | 文档索引切到 Celery + Redis broker | todo | — | 新增 `celery_app.py` + tasks |
| P1-6 | 前端答案区加 👍/👎 按钮，写入 evaluation | todo | — | 改 `Chat.jsx` + 新增 `routers/feedback.py` |
| P1-7 | agent 链路打通 auto_merge_service（Small-to-Big） | todo | — | 改 retrieve/answer node |

---

## P2 阶段

| 编号 | 任务 | 状态 | 实际改动文件 | 备注 |
|---|---|---|---|---|
| P2-1 | 向量库抽象层，迁移到 Qdrant/Milvus/pgvector | todo | — | 重构 `vector_store.py` |
| P2-2 | 多知识库 namespace（collection per KB） | todo | — | 新增 `models/knowledge_base.py` |
| P2-3 | RBAC：admin/editor/viewer 角色与权限装饰器 | todo | — | 改 `security.py` + `models/user.py` |
| P2-4 | CI 评估流水线（GitHub Actions / 本地脚本） | todo | — | 新增 `.github/workflows/eval.yml` |
| P2-5 | 文档版本管理 + reindex 策略 | todo | — | 改 `document_service.py` |
| P2-6 | 元数据过滤检索 API | todo | — | 改 `routers/search*.py` |

---

## P3 阶段

| 编号 | 任务 | 状态 | 实际改动文件 | 备注 |
|---|---|---|---|---|
| P3-1 | AB 实验框架（流量分桶） | todo | — | — |
| P3-2 | Prompt Injection 检测 | todo | — | 新增 guard 服务 |
| P3-3 | PII 脱敏（日志/trace） | todo | — | — |
| P3-4 | 多模态检索（表格/图片/代码块） | todo | — | — |
| P3-5 | 知识图谱增强检索 | todo | — | — |
| P3-6 | 配置中心 + 特性开关 | todo | — | — |

---

## 阻塞项

| 编号 | 任务 | 阻塞原因 | 待解决 |
|---|---|---|---|
| — | — | — | — |
