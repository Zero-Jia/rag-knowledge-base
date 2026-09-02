# Agent 交接说明

> **新 session 的 Agent 请先完整阅读本文件，再读 `03-task-backlog.md`。**

---

## 当前项目状态（最后更新：2026-09-02）

- 项目已完成 Self-RAG / Corrective RAG 基础能力
- 文档体系已建立（`/docs`），企业级改造进行中
- **当前进行阶段：P0（已完成 P0-1、P0-2）**
- P0-1 已完成：answer_node 输出 `[1][2]` inline citation，state 新增 `citations` 字段（index/chunk_id/text/source/score），非流式与 SSE trace 事件均返回；回归通过（20 case，answer_correctness 0.9，17/20 带引用）
- P0-2 已完成：新增 `grounding_check_node`，answer→grounding_check→(fallback|END)，LLM 判断答案是否被证据支持，不通过走 fallback；chat/cache/无证据场景短路放行，LLM/解析故障保守放行；state 新增 `grounding_passed`/`grounding_reason`；回归通过（20 case，20/20 grounding passed 无误杀，correctness 0.9 持平基线）
- **下一个待办任务：P0-3**

## 下一步优先做什么

按 `03-task-backlog.md` 中状态为 `todo` 的任务，按编号顺序推进。当前推荐起点：

### P0-3：检索租户隔离

- **位置**：`app/agent/tools/vector_tool.py`、`hybrid_tool.py` + `app/agent/nodes/retrieve_node.py` + `app/routers/chat.py` + `app/services/agent_chat_service.py`、`agent_stream_service.py`
- **目标**：检索时按 `user_id`/`tenant_id` 过滤，保证多租户数据隔离
- **要点**：
  - vector/hybrid 工具查询时加 ChromaDB `where={"user_id": user_id}`
  - `retrieve_node` 从 state 取 user_id（由 chat 入口注入）
  - chat 入口（router + service）把当前用户 id 注入 state
  - 不涉及 prompt 改动，无需跑评估回归
- 详细设计见 `03-task-backlog.md` 的"P0-3 详细设计"

### 推荐推进顺序

1. **P0-3 + P0-4**（租户隔离，可并行；P0-4 完成后把 citations.source 换成文档名）
2. **P0-5**（Langfuse 接入）→ 3. **P0-6**（token/成本统计）

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
