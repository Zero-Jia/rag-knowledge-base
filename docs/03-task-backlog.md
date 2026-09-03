# 任务清单

> **状态约定**：`todo` / `doing` / `done` / `blocked` / `skip`
> `skip` = 经评估后决定不做（保留记录，备后续按需重启）。
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
| P1-1 | 把 retrieve/rerank/keyword/search 改造成 LangGraph Tool | done | `app/agent/tools/__init__.py`、`app/agent/tools/_common.py`（新增）、`app/agent/tools/keyword_tool.py`（新增）、`app/agent/tools/vector_tool.py`、`app/agent/tools/hybrid_tool.py`、`app/agent/tools/rerank_tool.py`、`app/services/hybrid_retrieval.py` | 双轨并存：纯函数（graph quick path 继续用）+ `make_xxx_tool`/`build_retrieval_tools` 工厂（P1-2 ReAct 用）；user_id 闭包绑定不进 tool schema 防越权；Tool 返回紧凑 JSON；新增 keyword_search 独立工具；4 工具均不调 LLM 无 token 消耗；冒烟全过 + 评估 20/20 持平基线（0.9/0.9/0.8） |
| P1-2 | 引入 ReAct Agent，保留现有图为 quick path | done | `app/agent/react_agent.py`（新增）、`app/agent/routing.py`（新增）、`app/agent/graph.py`、`app/agent/state.py`、`app/agent/prompts.py`、`app/agent/nodes/classify_node.py`、`app/agent/nodes/fallback_node.py`、`app/agent/debug.py`、`app/agent/tools/__init__.py`、`app/agent/tools/_common.py`、`app/agent/tools/hybrid_tool.py`、`app/agent/tools/vector_tool.py`、`app/agent/tools/keyword_tool.py`、`app/agent/tools/rerank_tool.py`、`app/core/config.py`、`app/services/agent_stream_service.py` | 图内加节点方案：三层漏斗路由（规则脚本+LLM 前置保守升级 / expansion 后证据不足升级 / grounding 失败升级），`react_attempted` 护栏保证 ReAct 最多一次，ReAct 证据复用 quick path 统一答案合成（prompt_builder + generate_answer_with_usage）后过同一 grounding 门控；开关 `REACT_AGENT_ENABLED=False` 默认关闭零调用；SSE 发 deep_research 过渡事件；冒烟全过 + 开关关闭评估 20/20 持平基线（0.9/0.9/0.8、零升级） |
| P1-3 | grade 分数 / fallback 率 / 延迟持久化到 DB | done | `app/models/metric.py`（新增）、`app/models/__init__.py`、`app/main.py`、`app/services/metric_service.py`（新增）、`app/services/chat_session_service.py`、`app/services/agent_memory_service.py`、`app/services/agent_chat_service.py`、`app/services/agent_stream_service.py` | 新增 `AgentMetric` 表（一行=一轮 assistant 请求），从 agent 最终 state+rag_trace+debug_info 提取 route/cache_hit/need_react/react_attempted/react_reason/react_trigger_reason/react_status/react_tool_rounds/react_evidence_count/evidence_grade/grade_metrics/grounding_passed/grounding_reason/need_fallback/fallback_reason/total_latency_ms/node_timings/token_prompt/completion/total 落库；`save_turn` 改返回 `Optional[ChatMessage]` 向后兼容，调用方接住 id 关联 metric 行；成功+失败两条路径都写入（失败标 error + need_fallback，无 chat_message_id）；写入异常静默不影响主流程；不存原文答案（PII 考量，原文由 chat_messages 持有）；SQLite 沿用 `Base.metadata.create_all` 自动建表无 alembic；不改 graph/prompt/retrieval/quick path，评估脚本直接调 graph.invoke 不经改动层，冒烟端到端验证落库正确（route/grade/grounding/latency/token 全字段正确提取） |
| P1-4 | 监控大盘 API（聚合指标查询） | done | `app/schemas/metrics.py`（新增）、`app/routers/metrics.py`（新增）、`app/services/metric_service.py`、`app/main.py`、`frontend/src/api/metrics.js`（新增）、`frontend/src/pages/Metrics.jsx`（新增）、`frontend/src/App.jsx`、`frontend/src/App.css` | 4 个只读端点（summary/timeseries/recent/react）聚合 `agent_metrics` 表；鉴权复用 `get_current_user` 默认按 current_user.id 过滤（租户隔离）；DB 层用 `func.avg`/`func.count`/`func.date` 聚合；ReAct 对比端点分 react_attempted True/False 两组对比 + delta；P95 用 Python 简单分位数计算（避免引入 numpy）；前端新增 Metrics 页（Summary 卡片网格 + ReAct 对比表 + 每日柱状图 + 最近 20 条明细表），原生 SVG/CSS 不引入图表库；App.jsx 侧边栏加 metrics 导航；不改 agent/graph/prompt/retrieval，无 DB schema 变更，无需评估回归；后端 4 端点路由注册验证通过 + service 层 4 函数冒烟返回正确结构 + 前端 vite build 通过（30 modules） |
| P1-5 | 文档索引切到 Celery + Redis broker | skip | — | 秋招项目无大文件并发索引需求，暂不做（2026-09-04 评估） |
| P1-6 | 前端答案区加 👍/👎 按钮，写入 evaluation | skip | — | 秋招项目无实际用户，反馈回流闭环无数据来源，暂不做（2026-09-04 评估） |
| P1-7 | agent 链路打通 auto_merge_service（Small-to-Big） | done | `scripts/verify_auto_merge_p1_7.py`（新增）、`scripts/reindex_hierarchy_p1_7.py`（新增）、`app/services/metric_service.py`、`app/schemas/metrics.py`、`frontend/src/pages/Metrics.jsx` | 验证先行：发现代码链路全通（hybrid/vector 检索层默认 enable_auto_merge=True、ReAct 工具复用同一纯函数、rerank/grade/citations 字段透传完备），真正断点是数据——现有文档为旧版 non-hierarchy 索引，ParentChunk 表 0 行，merge 触发率 0/20；写层级重索引脚本重建 33 文档（doc37 源文件丢失跳过），ParentChunk 0→184 行，merge 触发率 20/20，父块 rerank 分数无失真（8.x vs 子块 7.x），citations 正确指向父块（doc7_l1_0 等）；大盘观测补齐：summary 端点+前端卡片新增 auto_merge_requests/parent_chunks/rate（grade_metrics JSON Python 层解析）；无 DB schema 变更（ParentChunk 表已存在仅补数据）、无 prompt 改动 |

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
