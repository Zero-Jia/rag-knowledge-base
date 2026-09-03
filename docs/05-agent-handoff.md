# Agent 交接说明

> **新 session 的 Agent 请先完整阅读本文件，再读 `03-task-backlog.md`。**

---

## 当前项目状态（最后更新：2026-09-04）

- 项目已完成 Self-RAG / Corrective RAG 基础能力
- 文档体系已建立（`/docs`），企业级改造进行中
- **当前进行阶段：P1 阶段收尾完成（P1-1~P1-4、P1-7 已完成；P1-5、P1-6 经评估标记 skip），下一步进入 P2-1 向量库抽象层**
- P0-1 已完成：answer_node 输出 `[1][2]` inline citation，state 新增 `citations` 字段（index/chunk_id/text/source/score），非流式与 SSE trace 事件均返回；回归通过（20 case，answer_correctness 0.9，17/20 带引用）
- P0-2 已完成：新增 `grounding_check_node`，answer→grounding_check→(fallback|END)，LLM 判断答案是否被证据支持，不通过走 fallback；chat/cache/无证据场景短路放行，LLM/解析故障保守放行；state 新增 `grounding_passed`/`grounding_reason`；回归通过（20 case，20/20 grounding passed 无误杀，correctness 0.9 持平基线）
- P0-3 已完成：检索层 user_id 透传 + ChromaDB where 过滤（retrieval_service/hybrid_retrieval/vector_tool/retrieve_node），user_id None 兼容旧数据；评估 user_id=1 correctness 0.9 持平基线
- P0-4 已完成：indexing non-hierarchy 写 user_id metadata + vector_store update_metadatas + reindex 脚本回填 169 chunks；hierarchy 路径 _base_metadata 已写 user_id；Document model 已有 user_id 无需改
- P0-5 已完成：新增 `app/services/langfuse_service.py` 封装 Langfuse v4 SDK（`get_client()` + `start_observation()`），新增 4 个配置项 `LANGFUSE_ENABLED`/`LANGFUSE_HOST`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`；选 Langfuse Cloud Hobby 部署（非本地自建）；渐进式开关 `LANGFUSE_ENABLED=False` 默认关闭，开关关闭时零 SDK 初始化/零网络调用；agent_chat/stream_service 在 try 末尾成功路径 + except 失败路径各调一次 `report_agent_trace` 上报顶层 Trace；不上报原文 chunk 全文为 PII 脱敏预留；后端 `Application startup complete` 通过；评估回归 20/20 通过，correctness 0.9/rerank_recall 0.8/retrieval_recall 0.9 全持平基线
- P0-6 已完成：`rag_trace` 新增 `token_usage`（model/total/by_node），新增 `generate_answer_with_usage` 返回 usage；5 个 LLM 节点（classify/rewrite/answer/grounding_check/hyde_expand）调 `record_token_usage` 写 by_node+total；按用户要求**只统计 token 不算成本**（cost_usd 移除）；新增 `GET /chat/agent/sessions/{id}/usage` session 级聚合；前端 TracePanel 加 Session total + Token usage 区块；零 DB schema 变更（写进现有 rag_trace JSON 列）；评估 20/20 correctness 0.9/recall 0.9/rerank 0.8 持平基线
- P1-1 已完成：检索能力 Tool 化，双轨并存——纯函数（`vector_search_tool`/`hybrid_search_tool`/`keyword_search_tool`/`rerank_tool`，graph quick path 继续直接调用，一行未动）+ LangChain `StructuredTool` 工厂（`make_xxx_tool` / `build_retrieval_tools(user_id, rag_trace=None)`，返回紧凑 JSON 供 ReAct ToolMessage）；新增 `keyword_search` 独立工具（keyword_recall public 入口）；user_id 服务端闭包绑定、不进 tool schema 防越权（冒烟验证 user_id=999 跨租户无结果）；Tool 异常均返回 `{"error":...}` 不抛异常；4 工具均不调 LLM，P0-6 token 统计无需改动；graph/state/prompts/DB schema 零变更；评估 20/20 correctness 0.9/recall 0.9/rerank 0.8 持平基线
- P1-2 已完成：图内新增 `react_agent` 节点（`app/agent/react_agent.py`，invoke `create_react_agent` 子图绑定 4 检索工具），quick path 完整保留；**三层漏斗自动路由**——前置升级（classify：`app/agent/routing.py` 规则脚本 3 条硬信号 + LLM JSON 输出 need_react 软信号，规则优先、保守、闲聊不升级）、后置升级 1（expansion 二轮后 grade 证据不足）、后置升级 2（grounding 失败）；`react_attempted` 护栏保证 ReAct 最多一次，仍失败→fallback（react_no_evidence/react_error 文案）；**ReAct 只负责收集证据（拆问/多轮/换工具/多跳），最终答案复用 quick path 统一合成**（prompt_builder + generate_answer_with_usage），引用 [N] 与证据 index 确定性一致，再过同一 grounding 门控；总开关 `REACT_AGENT_ENABLED=False` 默认关闭（关闭时升级边全部回退、零调用）；SSE 新增 `deep_research` 过渡事件；无 DB schema 变更、无新依赖；开关关闭评估 20/20 持平基线（0.9/0.9/0.8、零升级），开关开启冒烟复合问题 8 轮工具/19 证据/citations 正确/grounding passed、越界问题诚实拒答
- P1-3 已完成：新增 `app/models/metric.py`（`AgentMetric` 表，一行=一轮 assistant 请求）+ `app/services/metric_service.py`（`persist_agent_metric` 从 agent 最终 state+rag_trace+debug_info 提取 route/cache_hit/need_react/react_attempted/react_reason/react_trigger_reason/react_status/react_tool_rounds/react_evidence_count/evidence_grade/grade_metrics/grounding/need_fallback/fallback_reason/total_latency_ms/node_timings/token_prompt/completion/total 落库）；`save_turn` 改返回 `Optional[ChatMessage]` 向后兼容（调用方接住 id 关联 metric 行）；成功+失败两条路径都写入（失败标 error+need_fallback，无 chat_message_id）；写入异常静默不影响主流程；不存原文答案（PII 考量，原文由 chat_messages 持有）；SQLite 沿用 `Base.metadata.create_all` 自动建表（migration 说明已写 04-progress-log）；不改 graph/prompt/retrieval/quick path；冒烟端到端验证落库正确（route/grade/grounding/latency/token 全字段正确，chat_message_id=18 成功关联）
- P1-4 已完成：新增 `app/routers/metrics.py`（4 个只读端点 `/metrics/summary`/`/timeseries`/`/recent`/`/react`）+ `app/schemas/metrics.py`（4 个响应模型）+ 扩展 `metric_service.py`（4 个聚合查询函数 `get_metrics_summary`/`get_metrics_timeseries`/`get_recent_metrics`/`get_react_comparison`，DB 层 `func.avg`/`func.count`/`func.date` 聚合，P95 用 Python 简单分位数避免 numpy）；鉴权复用 `get_current_user` 默认按 current_user.id 过滤（租户隔离）；ReAct 对比端点分 react_attempted True/False 两组 + delta；前端新增 `frontend/src/pages/Metrics.jsx`（Summary 卡片网格 + ReAct 对比表 + 每日柱状图原生 CSS 不引入图表库 + 最近 20 条明细表）+ `api/metrics.js` + App.jsx 侧边栏加 metrics 导航；无 DB schema 变更/无 agent/graph/prompt 改动；后端 4 端点路由注册验证通过 + service 层 4 函数冒烟返回正确结构 + 前端 vite build 通过（30 modules）
- P1-7 已完成（验证先行，实际改动远小于 backlog 预估）：**代码链路验证本来就全通**（quick path 检索层默认 enable_auto_merge=True；ReAct 经 P1-1 工厂复用同一纯函数天然同行为；rerank/grade/citations 字段透传完备；keyword_search 工具为有意不 merge 的设计决策），**真正断点是数据**——现有文档为旧版 non-hierarchy 索引，ParentChunk 表 0 行，merge 触发率 0/20；新增 `scripts/verify_auto_merge_p1_7.py`（四段式验证）+ `scripts/reindex_hierarchy_p1_7.py`（层级重索引，重建 33 文档，doc37 源文件丢失跳过），ParentChunk 0→184 行，merge 触发率 **20/20**，父块 rerank 分数无失真（8.x vs 子块 7.x），citations 正确指向父块，端到端 grounding passed；大盘观测补齐（summary 端点 + 前端 Auto-merge rate 卡片新增 `auto_merge_requests`/`auto_merge_parent_chunks`/`auto_merge_rate`）；无 DB schema 变更/无 prompt 改动；评估回归通过且 rerank 提升（correctness 0.9 持平、recall 0.9 持平、rerank_recall 0.8→0.85）
- **已知遗留**：ReAct 证据文本截断（`REACT_TOOL_TEXT_LIMIT=800`，merge 后父块最长 4000 字符进最终 prompt 时被截到 800），影响面待量化，可单开任务；`evaluate_agent_day18.py` 需 `PYTHONPATH=.` 方式运行（脚本无 sys.path 处理）
- **下一个待办任务：P2-1（向量库抽象层，重构 `vector_store.py`，可迁移 Qdrant/Milvus/pgvector）**

## 下一步优先做什么

按 `03-task-backlog.md` 中状态为 `todo` 的任务，按编号顺序推进。当前推荐起点：

### P2-1：向量库抽象层（迁移到 Qdrant/Milvus/pgvector）

- **位置**：重构 `app/services/vector_store.py`
- **目标**：把 ChromaDB 直接调用封装为向量库抽象层，为后续切换 Qdrant/Milvus/pgvector 做准备（企业级选型灵活性 + 面试亮点）
- **要点**：
  - 现有调用方：`retrieval_service.py`（search/get_texts）、`indexing_service.py`（add_texts/delete/update_metadatas）、`vector_tool`、`document_delete_service.py`
  - 建议先定义 `VectorStore` 抽象接口（add/search/delete/update/get），Chroma 作为第一个实现，接口签名保持现有方法兼容
  - 是否真的迁移到第二实现可评估 ROI；仅做抽象层重构也可作为 P2-1 的最小收尾
  - 向量库 schema 变更需提供 reindex 脚本（conventions 要求）；现有 `reindex_hierarchy_p1_7.py`/`reindex_user_metadata.py` 可参考

### 已 skip 任务（2026-09-04 评估）

- **P1-5（Celery 异步索引）**：秋招项目无大文件并发索引需求，暂不做
- **P1-6（前端反馈按钮）**：秋招项目无实际用户，反馈回流闭环无数据来源，暂不做

### P1 遗留可选项（非阻塞）

- **ReAct 证据文本截断**：`REACT_TOOL_TEXT_LIMIT=800` vs merge 后父块最长 4000 字符，ReAct 路径答案合成只拿到父块前 800 字符；quantify 影响后可单开小任务（方案：证据收集后按 chunk_id 回查补全文本）

### 推荐推进顺序

1. **P2-1**（向量库抽象层）→ P2-2（多知识库 namespace）→ P2 后续

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
