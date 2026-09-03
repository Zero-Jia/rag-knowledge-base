# Agent 交接说明

> **新 session 的 Agent 请先完整阅读本文件，再读 `03-task-backlog.md`。**

---

## 当前项目状态（最后更新：2026-09-04）

- 项目已完成 Self-RAG / Corrective RAG 基础能力
- 文档体系已建立（`/docs`），企业级改造进行中
- **当前进行阶段：P1 进行中（P1-1、P1-2 已完成），下一步 P1-3 指标持久化（grade 分数 / fallback 率 / react 触发率 / 延迟落 DB）**
- P0-1 已完成：answer_node 输出 `[1][2]` inline citation，state 新增 `citations` 字段（index/chunk_id/text/source/score），非流式与 SSE trace 事件均返回；回归通过（20 case，answer_correctness 0.9，17/20 带引用）
- P0-2 已完成：新增 `grounding_check_node`，answer→grounding_check→(fallback|END)，LLM 判断答案是否被证据支持，不通过走 fallback；chat/cache/无证据场景短路放行，LLM/解析故障保守放行；state 新增 `grounding_passed`/`grounding_reason`；回归通过（20 case，20/20 grounding passed 无误杀，correctness 0.9 持平基线）
- P0-3 已完成：检索层 user_id 透传 + ChromaDB where 过滤（retrieval_service/hybrid_retrieval/vector_tool/retrieve_node），user_id None 兼容旧数据；评估 user_id=1 correctness 0.9 持平基线
- P0-4 已完成：indexing non-hierarchy 写 user_id metadata + vector_store update_metadatas + reindex 脚本回填 169 chunks；hierarchy 路径 _base_metadata 已写 user_id；Document model 已有 user_id 无需改
- P0-5 已完成：新增 `app/services/langfuse_service.py` 封装 Langfuse v4 SDK（`get_client()` + `start_observation()`），新增 4 个配置项 `LANGFUSE_ENABLED`/`LANGFUSE_HOST`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`；选 Langfuse Cloud Hobby 部署（非本地自建）；渐进式开关 `LANGFUSE_ENABLED=False` 默认关闭，开关关闭时零 SDK 初始化/零网络调用；agent_chat/stream_service 在 try 末尾成功路径 + except 失败路径各调一次 `report_agent_trace` 上报顶层 Trace；不上报原文 chunk 全文为 PII 脱敏预留；后端 `Application startup complete` 通过；评估回归 20/20 通过，correctness 0.9/rerank_recall 0.8/retrieval_recall 0.9 全持平基线
- P0-6 已完成：`rag_trace` 新增 `token_usage`（model/total/by_node），新增 `generate_answer_with_usage` 返回 usage；5 个 LLM 节点（classify/rewrite/answer/grounding_check/hyde_expand）调 `record_token_usage` 写 by_node+total；按 user 要求**只统计 token 不算成本**（cost_usd 移除）；新增 `GET /chat/agent/sessions/{id}/usage` session 级聚合；前端 TracePanel 加 Session total + Token usage 区块；零 DB schema 变更（写进现有 rag_trace JSON 列）；评估 20/20 correctness 0.9/recall 0.9/rerank 0.8 持平基线
- P1-1 已完成：检索能力 Tool 化，双轨并存——纯函数（`vector_search_tool`/`hybrid_search_tool`/`keyword_search_tool`/`rerank_tool`，graph quick path 继续直接调用，一行未动）+ LangChain `StructuredTool` 工厂（`make_xxx_tool` / `build_retrieval_tools(user_id, rag_trace=None)`，返回紧凑 JSON 供 ReAct ToolMessage）；新增 `keyword_search` 独立工具（keyword_recall public 入口）；user_id 服务端闭包绑定、不进 tool schema 防越权（冒烟验证 user_id=999 跨租户无结果）；Tool 异常均返回 `{"error":...}` 不抛异常；4 工具均不调 LLM，P0-6 token 统计无需改动；graph/state/prompts/DB schema 零变更；评估 20/20 correctness 0.9/recall 0.9/rerank 0.8 持平基线
- P1-2 已完成：图内新增 `react_agent` 节点（`app/agent/react_agent.py`，invoke `create_react_agent` 子图绑定 4 检索工具），quick path 完整保留；**三层漏斗自动路由**——前置升级（classify：`app/agent/routing.py` 规则脚本 3 条硬信号 + LLM JSON 输出 need_react 软信号，规则优先、保守、闲聊不升级）、后置升级 1（expansion 二轮后 grade 证据不足）、后置升级 2（grounding 失败）；`react_attempted` 护栏保证 ReAct 最多一次，仍失败→fallback（react_no_evidence/react_error 文案）；**ReAct 只负责收集证据（拆问/多轮/换工具/多跳），最终答案复用 quick path 统一合成**（prompt_builder + generate_answer_with_usage），引用 [N] 与证据 index 确定性一致，再过同一 grounding 门控；总开关 `REACT_AGENT_ENABLED=False` 默认关闭（关闭时升级边全部回退、零调用）；SSE 新增 `deep_research` 过渡事件；无 DB schema 变更、无新依赖；开关关闭评估 20/20 持平基线（0.9/0.9/0.8、零升级），开关开启冒烟复合问题 8 轮工具/19 证据/citations 正确/grounding passed、越界问题诚实拒答
- **下一个待办任务：P1-3（grade 分数 / fallback 率 / react 触发率 / 延迟持久化到 DB）**

## 下一步优先做什么

按 `03-task-backlog.md` 中状态为 `todo` 的任务，按编号顺序推进。当前推荐起点：

### P1-3：grade 分数 / fallback 率 / 延迟持久化到 DB

- **位置**：新增 `app/models/metric.py`（评估通过后）
- **目标**：把每轮请求的 grade 分数、grounding 结果、fallback 触发、react 触发（need_react/react_reason/react_tool_rounds/react_evidence_count）、各节点延迟与 token 落库，支撑每日报表与 ReAct vs quick path 效果对比
- **要点**：
  - 涉及 DB schema 变更，开工前必须先告知用户并写 migration 说明
  - react 相关字段已全部在 AgentState/debug_info/rag_trace 中（P1-2），持久化时直接取用
  - 为后续灰度决策（REACT_AGENT_ENABLED 是否常开）提供数据：ReAct 触发率、抢救率、token 成本

### 推荐推进顺序

1. **P1-3**（指标持久化）→ 2. P1-4（监控大盘 API）→ P1 其余任务（P1-5 Celery / P1-6 反馈按钮 / P1-7 Small-to-Big）

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

- **不要破坏现有 graph.py 的 quick path**：P1-2 已完成 ReAct 节点与三层漏斗路由，quick path 静态编排在开关关闭时必须逐字节走原链路（升级边由 `REACT_AGENT_ENABLED` + `react_attempted` 双重护栏）；后续迭代不得用 ReAct 替换静态图，改路由时保持 `predict_react_upgrade` 单点判定
- **不要破坏现有 API 契约**：改动需向后兼容，新字段以可选形式加入
- 涉及数据库 schema 变更必须先写 migration 说明到 `04-progress-log.md`
- 涉及第三方依赖新增必须先确认 `requirements.txt` 是否合理
- 涉及 prompt 改动必须跑一次 `scripts/evaluate_agent_day18.py` 回归
- 流式输出（`agent_stream_service.py`）改动需同步考虑 SSE 事件格式

## 现有 graph 结构（P1-2 后：quick path + react_agent 节点）

```text
classify（规则脚本 + LLM JSON：route / need_react）
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
                                   react_agent（create_react_agent 子图：
                                   自主拆问/多轮 4 工具/换词/多跳收集证据
                                   → build_messages 统一合成答案）
                                   -> grounding_check -> (fallback | END)
```

> 升级护栏：`react_attempted` 状态位保证 ReAct 全程最多一次（`_can_upgrade_to_react`）；总开关 `REACT_AGENT_ENABLED=False` 时三条升级边全部回退到原 quick path。路由判定单点 `predict_react_upgrade(prev_node, state)` 供图条件边与 SSE deep_research 事件复用。
>
> P0-2 的 grounding_check 校验边、P1-2 的 react_agent 升级边均为任务范围内的图扩展，quick path 静态编排完整保留。

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
