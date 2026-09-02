# 开发进度日志

> 每个 session 开发结束追加一条记录，**最新在最上面**。

## 记录模板（复制使用）

```
### Session YYYY-MM-DD
- **目标**：本 session 要做什么
- **完成任务**：
  - [编号] 任务名 — 改动文件
- **未完成/遗留**：
  - 原因 + 下次继续点
- **关键决策**：如果有架构/技术选型决策记录在此
- **遇到的问题**：踩坑记录，避免下次重复
- **下一步建议**：下个 session 优先做什么
```

---

### Session 2026-09-02（P0-3 + P0-4 检索租户隔离）

- **目标**：完成 P0-3（检索 where 过滤）+ P0-4（数据写 user_id metadata）合并闭环
- **完成任务**：
  - [P0-3] 检索层 user_id 透传 + ChromaDB where 过滤 — 改动文件：
    - `app/services/retrieval_service.py`：`retrieve_chunks`/`retrieve_all_chunks` 加 `user_id` 参数，user_id 非 None 时 `store.search/get_texts` 传 `where={"user_id": user_id}`，None 兼容旧数据
    - `app/services/hybrid_retrieval.py`：`_keyword_recall`/`hybrid_retrieve` 把 user_id 传给 vector_recall 与 keyword_recall（原先只用于 cache key）；`HYBRID_CACHE_VERSION` v5→v6 使旧缓存失效
    - `app/agent/tools/vector_tool.py`：`vector_search_tool` 加 `user_id` 参数
    - `app/agent/nodes/retrieve_node.py`：vector 回退分支传 user_id（hybrid 分支此前已传）
  - [P0-4] 数据写 user_id metadata — 改动文件：
    - `app/services/indexing_service.py`：non-hierarchy 分支构造 `leaf_metadatas` 显式带 `user_id: doc.user_id`（hierarchy 路径 `_base_metadata` 已写 user_id，无需改）
    - `app/services/vector_store.py`：新增 `update_metadatas(ids, metadatas)` 方法（Chroma `collection.update` 封装）
    - `scripts/reindex_user_metadata.py`（新增）：一次性回填脚本，遍历现有 chunks 按 document_id 查 Document 表拿 user_id，回填 metadata（不重新 embedding，幂等）
    - 注：`Document` model 已有 `user_id` 字段，`text_processing._base_metadata` 已写 user_id，无需改
- **关键决策**：
  - P0-3 + P0-4 合并做：检索过滤依赖数据带 user_id，单独做 P0-3 会导致登录用户检索全空
  - user_id None 时不过滤：保护未登录/评估/旧数据场景（向后兼容，渐进式激活）
  - reindex 只更新 metadata 不重新 embedding：节省 token，169 chunks 秒级完成
  - 升 HYBRID_CACHE_VERSION v5→v6：强制旧缓存失效，确保评估走新 where 过滤
- **数据现状**：现有 34 个 Document 全部 user_id=1（169 chunks），reindex 前无 user_id metadata，reindex 后全部回填 user_id=1
- **评估回归**（`scripts/evaluate_agent_day18.py`，评估传 user_id=1，where 命中等价全库）：
  - 20 case 全通过，无 error，无 grounding 误杀
  - avg_answer_correctness 0.9、avg_retrieval_recall@8 0.9、avg_rerank_recall@5 0.8（与基线完全持平，无回归）
  - grounding 20/20 passed，0/20 grounding_failed fallback
- **未完成/遗留**：
  - 租户隔离的"跨租户不可见"端到端验证需多用户数据（当前仅 user_id=1）；建议 P1 阶段补一个 user_id=2 的隔离测试用例
  - citations.source 仍为 document_id（文档名替换待后续迭代，P0-4 已写入 user_id metadata，数据层就绪）
- **下一步建议**：
  1. P0-5（Langfuse 接入）→ P0-6（token/成本统计），P0 阶段收尾
  2. P0 完成后进入 P1（ReAct agent 改造）

---

### Session 2026-09-02（P0-2 groundedness 校验）

- **目标**：完成 P0-2，答案生成后做 faithfulness 校验，不通过则走 fallback
- **完成任务**：
  - [P0-2] groundedness 校验 — 改动文件：
    - `app/agent/state.py`：新增可选字段 `grounding_passed: bool` 与 `grounding_reason: Optional[str]`（向后兼容）
    - `app/agent/prompts.py`：新增 `GROUNDING_CHECK_SYSTEM_PROMPT` 与 `build_grounding_check_messages()`，要求 LLM 输出严格 JSON `{"supported": bool, "reason": str}`；明确拒答不算幻觉（supported=true）
    - `app/agent/nodes/grounding_check_node.py`（新增）：answer 后的 grounding 校验节点，LLM 判断答案是否被 reranked_docs 支持；chat/cache_hit/无证据/空答案场景短路放行；LLM 故障或 JSON 解析失败保守放行（不阻断主流程）；不通过则设 need_fallback=True + fallback_reason="grounding_failed"
    - `app/agent/nodes/fallback_node.py`：reason_to_message 新增 `grounding_failed` 兜底文案
    - `app/agent/graph.py`：注册 grounding_check 节点，边 answer→grounding_check，条件边 route_after_grounding → (fallback | END)
    - `app/agent/debug.py`：build_agent_debug_summary 暴露 grounding_passed/grounding_reason/grounding_status
    - `app/services/agent_stream_service.py`：SSE trace 事件 + step_payload debug 暴露 grounding 结果
    - `app/services/agent_chat_service.py`：非流式 payload 暴露 grounding_passed/grounding_reason
- **未完成/遗留**：
  - 流式场景 grounding 在 answer 流式输出完成后执行，仅在最终 trace 事件记录结果，不撤改已吐给前端的答案（撤回流式不现实）；未来若需"不合规答案不展示"需改流式架构
  - `answer_node` 的 `save_agent_cache` 在 grounding 之前调用，若 grounding 失败走 fallback，缓存里仍存原 answer；精确缓存命中时不再过 grounding。属可接受权衡（精确缓存命中率低），P1 阶段考虑把缓存写入时机后移到 grounding 通过后
  - 评估集为知识库内问题，无幻觉 case，grounding 20/20 全 passed（符合预期）；grounding 的真实拦截价值需在生产环境验证
- **关键决策**：
  - 用独立 `grounding_check_node` 而非内嵌 `answer_node`：职责分离，图结构清晰，便于 trace
  - grounding LLM 用 `temperature=0.0` 保证判断稳定
  - 保守放行策略：LLM/解析故障不阻断主流程（grounding 坏了不能比没有更糟），reason 标记 `llm_error_pass_through` / `parse_error_pass_through`
  - JSON 解析容错：先 `json.loads`，失败用正则提 `supported` 字段，再失败放行
  - 拒答答案（"无法回答"）在 prompt 里明确判 supported=true，避免误杀诚实拒答
  - 不破坏 quick path：P0-2 在 answer 末尾加校验边，是任务范围内的图扩展，非 P1-1 的 ReAct 改造
- **遇到的问题**：
  - Windows PowerShell `>` / `|` 重定向 python 输出会因编码/管道转码丢内容（UTF-16、行丢失），改用 python 内 `sys.stdout=f` 重定向 + `runpy.run_path` 执行脚本，最后 `f.flush()/f.close()` 保证 20 case 全写盘
  - `python scripts/xxx.py` 直接运行时 sys.path[0] 是 scripts 目录，找不到 `app` 包，需 `sys.path.insert(0,'.')` 或设 PYTHONPATH
- **评估回归**（`scripts/evaluate_agent_day18.py`，涉及 prompt 新增必跑）：
  - 20 case 全部通过，无 error，无 grounding 误杀
  - avg_answer_correctness 0.9、avg_retrieval_recall@8 0.9、avg_rerank_recall@5 0.8（与 P0-1 基线完全持平，无回归）
  - grounding 分布：20/20 case grounding_status=passed，0/20 failed，0/20 触发 grounding_failed fallback
- **下一步建议**：
  1. 做 P0-3 + P0-4（租户隔离，可并行），P0-4 完成后把 citations.source 换成文档名
  2. P0-5（Langfuse 接入）→ P0-6（token/成本统计）

---

### Session 2026-09-02（P0-1 引用溯源）

- **目标**：完成 P0-1，让 answer_node 输出带 `[1][2]` 引用的答案，并在 state 中维护 `citations` 字段
- **完成任务**：
  - [P0-1] answer_node 输出 inline citation 映射 chunk_id — 改动文件：
    - `app/agent/state.py`：新增 `citations: List[Dict[str, Any]]` 可选字段
    - `app/agent/nodes/answer_node.py`：新增 `build_citations()`，LLM 返回后解析 `[N]` 标记映射回 context_docs，写入 `state["citations"]`；chat 分支置空列表
    - `app/agent/nodes/cache_node.py`：精确缓存命中时用缓存 chunks + 缓存答案重建 citations；语义缓存命中置空
    - `app/services/prompt_builder.py`：context 改为 `[1]...[N]` 编号；system + user prompt 加引用输出要求（中文指令 + few-shot 示例）
    - `app/services/retrieval_service.py`：metadata 缺 `chunk_id` 时用 Chroma 文档 id 兜底（旧数据 `doc{id}_chunk{i}`，新数据 id 即 chunk_id）
    - `app/services/hybrid_retrieval.py`：`HYBRID_CACHE_VERSION` 升为 `hybrid_v5_citation_chunk_id`，使旧检索缓存条目（无 chunk_id）失效
    - `app/services/agent_chat_service.py`：非流式 payload 返回 `citations`（向后兼容）
    - `app/services/agent_stream_service.py`：SSE `trace` 事件（最后一个数据事件，done 之前）返回 `citations`
- **未完成/遗留**：
  - citations.source 暂为 document_id（检索结果无文档名），P0-4 补充文档 metadata 后替换
  - 3/20 评估 case 答案无引用标记，均为拒答或极短答案场景，属预期行为
- **关键决策**：
  - 引用指令放在 `prompt_builder.py` 而非 `prompts.py`：`answer_node` 实际调用的是 `build_messages`，`prompts.py` 只有 classify/rewrite prompt
  - context 编号用 1-based 顺序编号（非 document_id），保证 LLM 标记与 citations.index 一一对应
  - 缓存命中也返回 citations：精确缓存 payload 自带 chunks 可重建；语义缓存无 chunks 置空
  - Chroma `query/get` 的 include 不支持 `"ids"`（会抛 ValueError），但响应默认自带 ids，直接读取即可，vector_store.py 无需改动
- **遇到的问题**：
  - Windows 下 PowerShell `>` 重定向原生进程输出会丢内容（仅剩 8 字节），改用 Python subprocess `capture_output=True` 捕获
  - 环境：项目无独立 venv，实际跑在 conda base（D:\conda）；本次补装了 redis/chromadb/jieba/sentence-transformers/rank-bm25/pypdf/transformers/onnxruntime/mmh3（均为 requirements.txt 已声明依赖）
  - hybrid 检索有结果缓存，改 chunk_id 字段后必须升 `HYBRID_CACHE_VERSION`，否则命中旧条目拿不到新字段
- **评估回归**（`scripts/evaluate_agent_day18.py`，涉及 prompt 改动必跑）：
  - 20 case 全部通过，无 error
  - avg_answer_correctness 0.9、avg_retrieval_recall@8 0.9、avg_rerank_recall@5 0.8（与改动前基线持平，无回归）
  - 17/20 case 答案带 `[N]` 引用且 citations 正确生成（含 chunk_id / 原文 / document_id / rerank_score）
- **下一步建议**：
  1. 做 P0-2（groundedness 校验），与 P0-1 共用 answer_node 出口
  2. P0-3/P0-4（租户隔离）可并行，P0-4 完成后把 citations.source 换成文档名

---

### Session 2026-09-02（基线建立）

- **目标**：建立项目开发文档体系，梳理与企业级 Agentic RAG 的差距
- **完成任务**：
  - 创建 `/docs` 文件夹与全部 markdown 文档（README / 00-overview / 01-gap-analysis / 02-roadmap / 03-task-backlog / 04-progress-log / 05-agent-handoff / 06-conventions）
  - 完成差距分析（`01-gap-analysis.md`）：识别 7 大差距，Agent 自主性、引用溯源、多租户为最高优先级
  - 完成路线图与任务清单（`02-roadmap.md`、`03-task-backlog.md`）：P0/P1/P2/P3 共 23 个任务
- **未完成/遗留**：本 session 为文档准备阶段，未动代码
- **关键决策**：
  - 采用 `/docs` markdown 作为跨 session 记忆库
  - 后续开发优先走 P0 阶段
  - `05-agent-handoff.md` 为 Agent 入口文件，第一个读
  - 任务粒度控制在 1-2 个 session 内可完成
- **遇到的问题**：无
- **下一步建议**：
  1. 从 P0-1（answer_node 引用溯源）开始，它是用户可感知价值最高的任务
  2. P0-1 完成后顺手做 P0-2（groundedness 校验），二者共用 answer_node 出口
  3. P0-3/P0-4（租户隔离）可并行推进，不依赖 P0-1/P0-2
