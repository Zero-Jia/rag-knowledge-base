# Agent 交接说明

> **新 session 的 Agent 请先完整阅读本文件，再读 `03-task-backlog.md`。**

---

## 当前项目状态（最后更新：2026-09-03）

- 项目已完成 Self-RAG / Corrective RAG 基础能力
- 文档体系已建立（`/docs`），企业级改造进行中
- **当前进行阶段：P0 已全部完成（P0-1 ~ P0-6），下一步进入 P1（ReAct agent 改造）**
- P0-1 已完成：answer_node 输出 `[1][2]` inline citation，state 新增 `citations` 字段（index/chunk_id/text/source/score），非流式与 SSE trace 事件均返回；回归通过（20 case，answer_correctness 0.9，17/20 带引用）
- P0-2 已完成：新增 `grounding_check_node`，answer→grounding_check→(fallback|END)，LLM 判断答案是否被证据支持，不通过走 fallback；chat/cache/无证据场景短路放行，LLM/解析故障保守放行；state 新增 `grounding_passed`/`grounding_reason`；回归通过（20 case，20/20 grounding passed 无误杀，correctness 0.9 持平基线）
- P0-3 已完成：检索层 user_id 透传 + ChromaDB where 过滤（retrieval_service/hybrid_retrieval/vector_tool/retrieve_node），user_id None 兼容旧数据；评估 user_id=1 correctness 0.9 持平基线
- P0-4 已完成：indexing non-hierarchy 写 user_id metadata + vector_store update_metadatas + reindex 脚本回填 169 chunks；hierarchy 路径 _base_metadata 已写 user_id；Document model 已有 user_id 无需改
- P0-5 已完成：新增 `app/services/langfuse_service.py` 封装 Langfuse v4 SDK（`get_client()` + `start_observation()`），新增 4 个配置项 `LANGFUSE_ENABLED`/`LANGFUSE_HOST`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`；选 Langfuse Cloud Hobby 部署（非本地自建）；渐进式开关 `LANGFUSE_ENABLED=False` 默认关闭，开关关闭时零 SDK 初始化/零网络调用；agent_chat/stream_service 在 try 末尾成功路径 + except 失败路径各调一次 `report_agent_trace` 上报顶层 Trace；不上报原文 chunk 全文为 PII 脱敏预留；后端 `Application startup complete` 通过；评估回归 20/20 通过，correctness 0.9/rerank_recall 0.8/retrieval_recall 0.9 全持平基线
- P0-6 已完成：`rag_trace` 新增 `token_usage`（model/total/by_node），新增 `generate_answer_with_usage` 返回 usage；5 个 LLM 节点（classify/rewrite/answer/grounding_check/hyde_expand）调 `record_token_usage` 写 by_node+total；按 user 要求**只统计 token 不算成本**（cost_usd 移除）；新增 `GET /chat/agent/sessions/{id}/usage` session 级聚合；前端 TracePanel 加 Session total + Token usage 区块；零 DB schema 变更（写进现有 rag_trace JSON 列）；评估 20/20 correctness 0.9/recall 0.9/rerank 0.8 持平基线
- **下一个待办任务：P1-1（P0 阶段已全部完成）**

## 下一步优先做什么

按 `03-task-backlog.md` 中状态为 `todo` 的任务，按编号顺序推进。当前推荐起点：

### P1-1：把 retrieve/rerank/keyword/search 改造成 LangGraph Tool

- **位置**：重构 `app/agent/tools/`
- **目标**：把检索/重排/关键词检索封装为标准 Tool，为 P1-2 ReAct agent 调用打基础
- **要点**：
  - 现有 `vector_tool` / `hybrid_tool` / `retrieval_service` / `hybrid_retrieval` 逻辑封装为 Tool 接口（含 user_id 透传 + 租户隔离）
  - 保留现有 graph 作为 quick path（P1-2 引入 ReAct 时并存）
  - Tool 化后 P0-6 的 token 统计需兼容（Tool 内部若调 LLM 也要 record_token_usage）

### 推荐推进顺序

1. **P1-1**（检索 Tool 化）→ 2. **P1-2**（引入 ReAct agent，保留现有图为 quick path）→ P1 阶段推进

## 开始开发前必做

1. 读 `00-overview.md` 了解项目结构与关键文件
2. 读 `03-task-backlog.md` 找到当前 todo 任务
3. 读 `06-conventions.md` 遵守开发规范
4. 浏览 `04-progress-log.md` 最近 2-3 条，避免重复劳动

## 开发结束后必做

1. 更新 `03-task-backlog.md`：任务状态（todo→doing→done）+ 实际改动文件
2. 在 `04-progress-log.md` **顶部**追加本 session 记录
3. 更新本文件 `## 当前项目状态` 与 `## 下一步优先做什么` 段落

## 注意事项

- **不要破坏现有 graph.py 的 quick path**：P1-1 才会引入 ReAct，P0 阶段保持现有图结构
- **不要破坏现有 API 契约**：改动需向后兼容，新字段以可选形式加入
- 涉及数据库 schema 变更必须先写 migration 说明到 `04-progress-log.md`
- 涉及第三方依赖新增必须先确认 `requirements.txt` 是否合理
- 涉及 prompt 改动必须跑一次 `scripts/evaluate_agent_day18.py` 回归
- 流式输出（`agent_stream_service.py`）改动需同步考虑 SSE 事件格式

## 现有 graph 结构（不可在 P0 阶段破坏）

```text
classify
  -> cache
       -> rewrite
       -> retrieve_initial
       -> rerank_initial
       -> grade_documents
            -> answer -> grounding_check -> (fallback | END)
            -> query_expansion
                 -> retrieve_expanded
                 -> rerank_expanded
                 -> grade_documents
            -> fallback
```

> P0-2 已在 answer 末尾加 grounding_check 校验边（任务范围内的图扩展，非 P1-1 ReAct 改造，quick path 结构未破坏）。

## 关键文件速查

| 需求 | 文件 |
|---|---|
| 改 Agent 流程 | `app/agent/graph.py` |
| 改 Agent 状态 | `app/agent/state.py` |
| 改某个节点 | `app/agent/nodes/<xxx>_node.py` |
| 改提示词 | `app/agent/prompts.py` |
| 改检索逻辑 | `app/agent/tools/*.py` + `app/services/*retrieval*.py` |
| 改 API 入口 | `app/routers/*.py` |
| 改数据模型 | `app/models/*.py` |
| 改前端 | `frontend/src/pages/*.jsx` |
