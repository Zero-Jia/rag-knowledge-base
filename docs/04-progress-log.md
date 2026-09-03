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

### Session 2026-09-04（P1-7 auto_merge/Small-to-Big 验证打通 + 观测补齐）

- **目标**：完成 P1-7——验证并打通 agent 链路（quick path + ReAct）的 auto_merge_service（Small-to-Big），补齐大盘观测
- **完成任务**：
  - [P1-7] 验证 + 数据修复 + 观测补齐 — 改动文件：
    - `scripts/verify_auto_merge_p1_7.py`（新增）：四段式验证脚本（数据层/检索层/rerank 层/端到端 citations），Part A-C 零 LLM，Part D 仅 2 case LLM
    - `scripts/reindex_hierarchy_p1_7.py`（新增）：对 status=DONE 文档重跑 `index_document_pipeline` 重建层级索引（支持 `REINDEX_DOC_IDS` 指定单文档）
    - `app/services/metric_service.py`：`get_metrics_summary` 新增 auto_merge 聚合（`grade_metrics` JSON 列 Python 层解析，SQLite 不支持 JSON 聚合）
    - `app/schemas/metrics.py`：`MetricSummary` 新增 3 字段 `auto_merge_requests`/`auto_merge_parent_chunks`/`auto_merge_rate`（向后兼容）
    - `frontend/src/pages/Metrics.jsx`：SummaryCards 新增 Auto-merge rate 卡片（复用现有样式）
- **关键发现（验证先行的价值）**：
  - **代码链路本来就是全通的**：quick path（`hybrid_retrieve` 默认 `enable_auto_merge=True`、`retrieve_chunks` 默认 `auto_merge=True`）、ReAct（P1-1 工厂复用同一纯函数 `hybrid_search_tool`，天然同行为）、rerank/grade/citations 字段透传完备（`grade_documents_node._build_grade_metrics` 已统计 `auto_merged_count`）——backlog 原描述"改 retrieve/answer node"已过时
  - **真正的断点是数据**：现有 34 文档均为 `HIERARCHICAL_CHUNKING_ENABLED` 生效前用 non-hierarchy 路径索引，`ParentChunk` 表 0 行、向量库 metadata 无层级字段 → merge 触发率 **0/20**（配置开关是开的，但无父块数据可查，`auto_merge_chunks` 空转）
  - 唯一有意不 merge 的工具：`keyword_search`（docstring 记录的设计决策：精确术语匹配场景合并父块反而稀释精度）
- **修复与验证结果**：
  - 重索引 33/34 文档成功（doc37 源文件物理丢失跳过，旧向量未删仍可用；doc5 ECCV PDF 产生 120 父块），`ParentChunk` 0→184 行
  - merge 触发率 **20/20**；小 txt 文档层级退化（L1≈全文≈L3 文本，无增益也无损失），大文档（PDF）真正受益（L2 父块 1000/2000 字符完整上下文）
  - rerank 层：父块 cross-encoder 分数普遍高于子块（P:8.x vs c:7.x），无"长文本打分失真被挤掉"问题（98 存活/51 挤出，挤出的多为同文档低分父块）
  - 端到端：`context_parent_count`=4-5，`grade_auto_merged_count` 正确统计，citations 命中父块（`doc7_l1_0`/`doc10_l1_0`），grounding passed，回答正常
  - 评估回归（20 case，PYTHONPATH=. 运行）：**通过且 rerank 提升**——answer_correctness 0.9（持平基线）、retrieval_recall 0.9（持平）、rerank_recall **0.8→0.85（+0.05）**，零回退
- **遇到的问题**：
  - `evaluate_agent_day18.py` 直接运行报 `ModuleNotFoundError: No module named 'app'`（脚本无 sys.path 处理），需 `PYTHONPATH=.` 或 `python -m` 方式运行——已记入本条，后续 session 注意
  - Redis 未启动时 search cache 静默降级（warning 刷屏但不阻塞），验证脚本可正常运行
- **未完成/遗留**：
  - ReAct 证据文本截断（`REACT_TOOL_TEXT_LIMIT=800`，父块 4000 字符进最终 prompt 时只剩前 800）——量化影响后决定是否单开任务
  - 前端 Chat 页未展示 auto_merged 标记（可选项，暂不做）
- **下一步建议**：
  1. P1 阶段收尾（P1-7 已完成，P1-5/P1-6 skip），进入 P2（向量库抽象层/多知识库 namespace 等，以 backlog P2 列表为准）

---

### Session 2026-09-04（文档维护：P1-5/P1-6 评估 skip + 下一步指向 P1-7）

- **目标**：评估 P1-5（Celery 异步索引）、P1-6（前端反馈按钮）对秋招项目的实际价值，决定是否推进；并校准下一步指向
- **完成任务**：
  - [文档] P1-5/P1-6 标记为 `skip` — 改动文件：
    - `docs/03-task-backlog.md`：状态约定新增 `skip`（=经评估后决定不做，保留记录备后续重启）；P1-5、P1-6 状态 todo→skip，备注列写明不做原因
    - `docs/05-agent-handoff.md`：当前项目状态段更新（P1-5/P1-6 标 skip）；"下一步优先做什么"重写为指向 P1-7（Small-to-Big），新增"已 skip 任务"小节
- **关键决策**：
  - **P1-5 跳过**：秋招项目无大文件并发索引需求，同步索引已够用；引入 Celery 增加部署复杂度（需常驻 worker 进程），ROI 低
  - **P1-6 跳过**：秋招项目无实际用户，👍/👎 反馈回流闭环无数据来源；P1-3 的 metric 表已提供机器视角指标，离线评估脚本已覆盖质量回归
  - **P1-7 现状校准**：经核查 `app/services/auto_merge_service.py` + `app/models/parent_chunk.py` 已存在，且 `app/services/retrieval_service.py`/`app/services/hybrid_retrieval.py` 已接入 auto_merge；但 `retrieve_node` 走的是 P1-1 的 `hybrid_search_tool`/`vector_search_tool`，P1-7 真正待办是打通 agent 节点链路对 auto_merge 的透传/引用映射（具体方案待动手时读 tools 确认）
- **未完成/遗留**：
  - P1-7 具体实现方案未定（待用户"确认"后读 `app/agent/tools/hybrid_tool.py`/`vector_tool.py` 核实 auto_merge 透传现状再给方案）
- **下一步建议**：
  1. P1-7：agent 链路打通 auto_merge_service（Small-to-Big），改 retrieve/answer node
  2. P1-7 完成后 P1 阶段收尾，进入 P2（向量库抽象层/多知识库 namespace 等）

---

### Session 2026-09-04（P1-4 监控大盘 API + 前端 Metrics 页）

- **目标**：完成 P1-4 — 把 P1-3 落库的 `agent_metrics` 表通过 4 个聚合查询 API 暴露，并在前端新增 Metrics 页可视化，支撑每日报表与 ReAct vs quick path 效果对比
- **完成任务**：
  - [P1-4] 监控大盘 API + 前端页 — 改动文件：
    - `app/schemas/metrics.py`（新增）：4 个 Pydantic 响应模型 `MetricSummary`（总数/fallback 率/react 触发率/抢救率/avg+p95 延迟/avg+total token/grounding 通过率/cache 命中率）、`MetricTimeseriesItem`（按日聚合项）、`MetricRecentItem`（明细行）、`ReactComparison`（quick_path+react 两组 `ReactGroupStats` + delta_latency_ms/delta_token_total）
    - `app/services/metric_service.py`：扩展 4 个聚合查询函数
      - `get_metrics_summary`：DB 层 `func.avg`/`func.sum` 聚合，`_apply_filters` 通用过滤拼装，P95 用 Python 简单分位数（`_percentile`，避免引入 numpy），空数据返回零值骨架
      - `get_metrics_timeseries`：`func.date(created_at)` 提取 YYYY-MM-DD 按日 group by，`func.cast(Bool, Integer)` 求和 fallback/react/grounding 计数
      - `get_recent_metrics`：按 created_at desc 取 N 条（limit clamped [1,200]），`_metric_row_to_dict` ORM→dict
      - `get_react_comparison`：react_attempted=True 一组、isnot(True) 一组（兼容 None），各自聚合 + react 组专属 avg_tool_rounds/avg_evidence_count/success_count/rescue_rate，delta 两组差值
    - `app/routers/metrics.py`（新增）：4 个 GET 端点 `/metrics/summary`、`/metrics/timeseries`、`/metrics/recent`、`/metrics/react`，全部 `Depends(get_current_user)` 鉴权，统一 `APIResponse` 包装，支持 query 参数 start/end(ISO)/session_id/limit
    - `app/main.py`：import + 注册 metrics router
    - `frontend/src/api/metrics.js`（新增）：4 个 API 函数 `getMetricsSummary`/`getMetricsTimeseries`/`getRecentMetrics`/`getReactComparison`，复用 `apiFetch`，`buildParams` 拼 query
    - `frontend/src/pages/Metrics.jsx`（新增）：Metrics 页 4 区块
      - 顶部工具栏：1/7/30 天范围切换 + Refresh
      - `SummaryCards`：10 张卡片网格（总请求/fallback 率/react 触发率/抢救率/avg 延迟/P95/avg token/total token/grounding 通过率/cache 命中率）
      - `ReactComparisonCard`：quick path vs ReAct 对比表（8 行指标 + delta 行）
      - `TimeseriesChart`：每日柱状图（总请求/fallback/react 三色叠加，原生 CSS 不引入图表库）
      - `RecentTable`：最近 20 条明细（时间/route/cache/grade/grounding/fallback/react/latency/token/session），fallback/react 用彩色 tag
    - `frontend/src/App.jsx`：import Metrics + `pages` 对象加 `metrics` 项（icon M）+ 侧边栏自动渲染 + 路由分支
    - `frontend/src/App.css`：追加 Metrics 页样式（toolbar/range-btn/summary-grid/card/ts-chart/ts-bar/recent-table/tag），复用现有 CSS 变量（--panel/--border/--accent/--text/--muted）
- **关键决策**：
  - **租户隔离**：复用 P0-3 原则，已登录用户默认按 `current_user.id` 过滤，`_apply_filters` 强制 user_id；项目无 RBAC（P2-3 才做），暂不开放全局查询，admin 视角留到 P2-3
  - **不引入图表库**：TimeseriesChart 用纯 CSS div 柱状图（总请求半透明底+fallback 橙+react 紫叠加），避免 recharts/chart.js 依赖膨胀（个人项目数据量小，简单柱状图够用）
  - **P95 用 Python 计算而非 numpy**：样本量小，`_percentile` 简单线性插值实现，避免引入 numpy 重依赖
  - **react 对比用 isnot(True) 而非 is_(False)**：兼容 react_attempted=None（开关关闭时旧数据/P1-3 失败行），把 None 归入 quick path 组符合语义
  - **空数据返回零值骨架而非 404**：summary 端点 total=0 时返回全 0 字段，前端 SummaryCards 仍能渲染（避免空页面）
  - **无 DB schema 变更、无 agent/graph/prompt 改动**：纯只读查询层 + 前端展示，不触及评估脚本路径，无需评估回归
  - **ISO 时间容错**：`_parse_time` 兼容带 Z/时区的 ISO 串，前端传 `toISOString()`（带 Z）可解析
- **验证**：
  - 后端 import 通过：`get_metrics_summary`/`get_metrics_timeseries`/`get_recent_metrics`/`get_react_comparison` + 4 个 schema 均可加载
  - 路由注册：`from app.main import app` 后 `app.routes` 含 4 个 `/metrics/*` 路径
  - service 层冒烟（临时脚本，跑完已删）：用 P1-3 落库的 user_id=1 数据调 4 个函数
    - summary: total_requests=1, grounding_pass_rate=1.0, avg_latency=11784.585ms, avg_token=1696
    - timeseries: 2026-09-03 一条，request_count=1
    - recent: 1 行明细，22 字段全返回
    - react: quick_path count=1, react count=0（开关关闭符合预期）, delta 为 null（react 组无样本）
  - 前端 vite build 通过：30 modules transformed，built in 655ms，无错误（仅 Browserslist 数据旧警告非错误）
- **未完成/遗留**：
  - 端到端前端实测（启动前后端在浏览器看 Metrics 页渲染）需用户启动前后端验证；本 session 仅代码就绪 + 构建通过
  - 日报表/告警（异常 fallback 率自动通知）留到后续
  - 多用户/全局视角的 admin 大盘留到 P2-3 RBAC 后
- **下一步建议**：
  1. P1-5：文档索引切到 Celery + Redis broker（异步任务队列，新增 `celery_app.py` + tasks）
  2. 或 P1-6：前端答案区 👍/👎 反馈按钮（结合 P1-3 metric 行做"低分答案"定位）

---

### Session 2026-09-04（P1-3 agent 指标持久化到 DB）

- **目标**：完成 P1-3 — 把每轮 agent 请求的关键指标（route/cache_hit/evidence_grade/grade 分数/grounding/fallback/react 触发情况/各节点延迟/token）落库成独立表 `agent_metrics`，为每日报表与 ReAct vs quick path 效果对比、`REACT_AGENT_ENABLED` 灰度决策提供数据
- **完成任务**：
  - [P1-3] agent 指标持久化 — 改动文件：
    - `app/models/metric.py`（新增）：`AgentMetric` 表，一行=一轮 assistant 请求。字段：id/chat_message_id(FK→chat_messages.id, nullable)/session_id/user_id/created_at + route/cache_hit + need_react/react_attempted/react_reason/react_trigger_reason/react_status/react_tool_rounds/react_evidence_count + evidence_grade/grade_metrics(JSON) + grounding_passed/grounding_reason + need_fallback/fallback_reason + total_latency_ms/node_timings(JSON)/token_prompt/token_completion/token_total + metadata_json（source/error）。三个索引 `(user_id,created_at)`/`(session_id,created_at)`/`(created_at)`
    - `app/models/__init__.py`：注册 `AgentMetric` re-export
    - `app/main.py`：`from app.models import ... metric ...` 显式 import 触发建表（`Base.metadata.create_all` 自动建表，无 alembic）
    - `app/services/metric_service.py`（新增）：`persist_agent_metric(state, session_id, user_id, chat_message_id, source, error, elapsed_ms)` 从 agent 最终 state 提取字段写入；`_safe_int/_safe_bool/_safe_float` 容错；`_extract_total_latency` 优先取 agent_total_ms/agent_stream_total_ms；写入异常 try/except 静默 log warning 不阻断主流程
    - `app/services/chat_session_service.py`：`save_turn` 改返回 `Optional[ChatMessage]`（向后兼容，之前无返回值）；assistant 行的 ChatMessage 含 id 供调用方关联 metric
    - `app/services/agent_memory_service.py`：re-export wrapper `save_turn` 同步改返回 `Optional[ChatMessage]`（透传）
    - `app/services/agent_chat_service.py`：成功路径接住 save_turn 返回的 chat_message_id，在 Langfuse 上报后调 `persist_agent_metric`；失败路径同样写一行（标 error + need_fallback，无 chat_message_id，做 locals 兜底防 NameError）
    - `app/services/agent_stream_service.py`：同上，成功路径（trace SSE 事件前）+ 失败路径（locals 兜底）各调一次 `persist_agent_metric`
- **DB schema 变更（migration 说明）**：
  - 新增表 `agent_metrics`（CREATE TABLE by `Base.metadata.create_all(bind=engine)` on startup；SQLite，无 alembic）
  - 字段定义见 `app/models/metric.py`；不动现有任何表（chat_sessions/chat_messages/documents/document_jobs/parent_chunks/users 均未改）
  - 关联：`agent_metrics.chat_message_id` 外键指向 `chat_messages.id`（nullable，失败路径无关联）
  - 既有 rag.db 重新启动后端即自动建表，无需手动跑 migration 脚本；既有数据不受影响
- **关键决策**：
  - **不存原文答案**：agent_metrics 只存标志/分数/延迟/token，原文由 chat_messages 表持有（已存于 rag_trace + content）；避免 PII 膨胀与重复存储
  - **save_turn 改返回值而非新增函数**：`save_turn` 之前无返回值，改为返回 `Optional[ChatMessage]` 是最小且向后兼容的改动；调用方接住 `.id` 即可关联，无需新增 helper 或在 service 层做"查最新 assistant 行"的脆弱查询
  - **失败路径也写 metric**：异常路径 state 可能为空 dict / final_session_id 可能未赋值，做 locals 兜底；失败行 chat_message_id=None 但标 error + need_fallback，用于统计失败率（与 Langfuse 失败上报对齐）
  - **写入异常静默**：metric 写入失败只 log warning 不抛异常，绝不影响 agent 主流程与 SSE 流（与 Langfuse 上报同样的容错原则）
  - **未改 graph/prompt/retrieval/quick path**：纯外围持久化层；评估脚本 `evaluate_agent_day18.py` 直接调 `agent_graph.invoke(state)` 不经 service 层，本次改动对其零影响
  - **延迟取值优先级**：优先调用方传入的 `elapsed_ms`（端到端 wall-clock 计时，最准），其次 rag_trace.timing 的 agent_total_ms/agent_stream_total_ms，最后 timing 各 stage 求和兜底
  - **react 相关字段从 debug_info 提取**：react_trigger_reason/react_status/react_tool_rounds/react_evidence_count 在 P1-2 已写入 debug_info（非 state 顶层），metric_service 从 `state.debug_info` 取；need_react/react_attempted/react_reason 在 state 顶层
- **验证**：
  - 全模块 import 通过（.venv python）：`AgentMetric` / `persist_agent_metric` / `agent_chat` / `stream_agent_chat_sse` 均可加载
  - 建表：`Base.metadata.create_all` 成功，`agent_metrics` 表已存在
  - 端到端冒烟（临时脚本，跑完已删）：`agent_chat("缓存分哪几种？", user_id=1)` → agent_metrics 写入 1 行，字段全字段正确提取：
    - route=kb_qa, cache_hit=False, evidence_grade=sufficient, grounding_passed=True, need_fallback=False
    - need_react=False, react_attempted=None（开关关闭符合预期）, react_tool_rounds=None
    - chat_message_id=18（成功关联到 chat_messages 表）
    - total_latency_ms=11784.585（端到端）, token_total=1696（从 rag_trace.token_usage.total 提取）
    - 注：该问题为知识库外问题，answer 为拒答（"没有关于缓存分类的信息"），grounding passed=True 符合 P0-2 拒答不算幻觉设计
  - 评估回归：本次未改 prompt/graph/retrieval，评估脚本直接调 graph.invoke 不经改动层，无需跑 20-case 回归（冒烟已端到端验证落库正确）
- **未完成/遗留**：
  - metric 查询/聚合 API 留到 P1-4（监控大盘 API，新增 `routers/metrics.py`）
  - 前端 TracePanel 暂未展示 metric 行（rag_trace 已有 token/grounding 展示，metric 表主要用于后端聚合报表与灰度决策数据）
  - 日报表/告警留到 P1-4 或后续
- **下一步建议**：
  1. P1-4：监控大盘 API（聚合 `agent_metrics` 表：日 fallback 率/react 触发率/平均延迟/token 消耗），新增 `routers/metrics.py`
  2. 数据积累后用 metric 表量化 ReAct vs quick path（开关开启跑一轮评估集对比 react 触发率/抢救率/token 成本）

---

### Session 2026-09-04（P1-2 ReAct Agent 与三层漏斗自动路由）

- **目标**：完成 P1-2 — 在现有 LangGraph StateGraph 内新增 `react_agent` 节点（invoke `create_react_agent` 子图，绑定 P1-1 的 4 个检索工具），实现 quick path（静态编排图）与 ReAct 双轨并存的**自动路由**；用户拍板方案：三层漏斗、两个后置升级点都要、图内加节点（不做独立端点）
- **完成任务**：
  - [P1-2] ReAct Agent + 三层漏斗路由 — 改动文件：
    - `app/agent/routing.py`（新增）：`detect_complex_query(question) -> Tuple[bool, str]` 规则脚本，3 条硬信号（问号≥2 → `rule_multi_question_mark`；比较词+连接词共现 → `rule_comparison`；并列连接词引导的多分句 → `rule_parallel_clause:*`），零 token、确定性
    - `app/agent/react_agent.py`（新增）：`build_react_agent(user_id, rag_trace)`（ChatOpenAI temperature=0.1，绑定 4 工具 text 截断 800 字符，REACT_SYSTEM_PROMPT，历史对话带 2 轮）；`react_agent_node` 入口置 `react_attempted=True`，`recursion_limit` 护栏（默认 25）；`_collect_evidence` 从 ToolMessage JSON 按 chunk_id 去重保序收集证据；`_sum_token_usage` 累加 AIMessage usage_metadata；**证据收集成功后复用 quick path 统一合成链路**（`build_messages` + `generate_answer_with_usage`）产出最终答案；成功回写 final_answer/reranked_docs/retrieved_docs/citations（`build_citations`），重置 need_fallback 交给 grounding_check 重新门控；无证据 → `react_no_evidence`，异常/空合成 → `react_error`，经 `_finalize_failure` 置 need_fallback
    - `app/agent/graph.py`：新增 `_react_enabled()`、`_can_upgrade_to_react(state)`（开关开 且 react_attempted 非 True）、`predict_react_upgrade(prev_node, state)`（SSE 复用，路由判定单点）；`route_after_cache` / `route_after_grade_documents` / `route_after_grounding` 三处条件边加 `"react_agent"` 升级分支；注册节点 + 条件边映射 + `add_edge("react_agent", "grounding_check")`；docstring 更新
    - `app/agent/nodes/classify_node.py`：重写。规则检测始终执行（写 debug）；LLM 分类改 JSON 输出 `{"route","need_react","reason"}`，`_parse_classify_output` 剥 ```json 围栏、json.loads 失败回退裸标签；`need_react = react_enabled and react_reason is not None and label != "chat"`（规则命中 reason 优先，否则 `llm_complex`；闲聊路由永不升级）；LLM 异常路径规则仍生效
    - `app/agent/prompts.py`：CLASSIFY_SYSTEM_PROMPT 改 JSON 输出 + 保守原则（拿不准 need_react=false）；新增 REACT_SYSTEM_PROMPT（agent 只负责拆问/多轮检索/换工具/多跳收集证据，收齐后停止调用工具并用一两句简述证据覆盖情况，**不自己撰写正式答案**）
    - `app/agent/state.py`：AgentState 新增 `need_react: bool`、`react_attempted: bool`、`react_reason: Optional[str]`
    - `app/agent/tools/`（`__init__.py`/`_common.py`/4 个工具文件）：工厂新增 `text_limit` 形参（ReAct 用 800，quick path 默认 300 不变），`build_retrieval_tools(text_limit=None)` 透传
    - `app/core/config.py`：新增 `REACT_AGENT_ENABLED=False`（默认关闭）、`REACT_RECURSION_LIMIT=25`、`REACT_TOOL_TEXT_LIMIT=800`
    - `app/agent/nodes/fallback_node.py`：新增 `react_no_evidence` / `react_error` 两条拒答文案
    - `app/agent/debug.py`：摘要新增 need_react/react_attempted/react_reason/react_status/react_trigger_reason/react_tool_rounds/react_evidence_count；日志摘要加 `react=.../rounds=.../reason=...`
    - `app/services/agent_stream_service.py`：导入 `predict_react_upgrade`；rag_step 后预测升级则发 `deep_research` SSE 事件（status/from_node/reason/trace_id）；trace 事件加 need_react/react_attempted/react_reason
- **关键决策**：
  - **图内加节点而非独立端点**：ReAct 是图中一个节点，与 quick path 共享缓存、grounding、fallback、token 统计、SSE 骨架；无 DB schema 变更、无新第三方依赖
  - **三层漏斗路由**：① 前置升级（classify：规则脚本硬信号 OR LLM need_react 软信号，规则优先、保守原则、闲聊不升级），cache miss 后直接进 ReAct；② 后置升级 1：grade_documents 在 expansion 二轮后证据仍不足 → ReAct；③ 后置升级 2：grounding_check 失败 → ReAct 重新检索合成。后置升级有效的根因：quick path 失败主因是召回机制失败（单 query 单向量单方向、expansion 开环盲试、无多意图拆解），ReAct 多子查询多方向、看结果闭环决策、按失败形态换工具、证据实体重述多跳；知识真不存在时 ReAct 同样失败 → fallback 拒答为终态
  - **`react_attempted` 状态位防环**：统一 `_can_upgrade_to_react` 护栏保证 ReAct 全程最多一次；ReAct 产出后无论成功失败都不再升级
  - **职责切分：ReAct 收集证据，答案合成复用 quick path**：开发中发现让 ReAct 自己写最终答案会出现过程性语句开头、正文 `doc11` 口语引用等格式漂移（即使 prompt 两次强化仍复发）。改为 agent 只做检索编排，收齐证据后用 `prompt_builder.build_messages` + answer 同款 prompt 统一合成——引用 [N] 与证据 index 严格一致（citations 确定性映射）、无过程语、grounding 行为与 quick path 完全对齐；ReAct 的自主性全部体现在证据收集阶段
  - **grounding 门控两条链路共享**：ReAct 答案同样过 grounding_check（空答案/cache_hit/chat 短路逻辑已核实兼容）；ReAct 失败（空答案+need_fallback）时 grounding 短路放行 → fallback
  - **总开关默认关闭**：`REACT_AGENT_ENABLED=False` 时所有升级边回到原 quick path，ReAct 零调用、零 token 风险；分类 LLM 仍输出 JSON 但 need_react 被开关与护栏忽略
- **验证**：
  - 规则脚本单测：4 hit（多问号/比较句/并列分句）+ 5 miss 全过
  - 开关关闭：图结构与路由全部走原路（单测断言）；`evaluate_agent_day18.py` 20 case 全执行，react_attempted=0、need_react=true=0、grounding failed=0，answer_correctness **0.9** / retrieval_recall@8 **0.9** / rerank_recall **0.8**，全部持平基线
  - 开关开启冒烟（复合问题"缓存分哪几种？语义缓存用的什么模型？fallback 什么时候触发？"）：前置命中 `rule_multi_question_mark` → ReAct 8 轮工具调用、19 条去重证据 → 统一合成答案无过程语、citations=2 正确映射（[7]→doc12、[10]→doc11）、grounding passed、need_fallback=False；token 记录完整（prompt 23729/completion 920，含合成）
  - SSE 冒烟（越界复合问题"量子计算的原理…？火星大气…？"）：事件序列 rag_step×3 → **deep_research**（from_node=cache，reason=rule_multi_question_mark）→ rag_step → content 流式 → trace → done；trace 中 react_attempted=true、need_react=true；证据为不相关片段时合成答案诚实拒答（"上下文未包含…"），grounding 放行，无幻觉
- **未完成/遗留**：
  - 后置升级点 1/2（grade 证据不足 / grounding 失败 → ReAct）的路由谓词已单测覆盖，但未构造 e2e 场景实测触发（需 mock 召回失败）；节点本身成功/失败路径已由前置升级 e2e 覆盖
  - ReAct 触发率与抢救率尚无数据：开关开启跑评估集/线上灰度后，用 P1-3 metrics（fallback 率/grade 分数/react_tool_rounds）量化对比
  - `REACT_TOOL_TEXT_LIMIT=800` 为冒烟经验值，后续按证据充分性再调
- **下一步建议**：
  1. P1-3：grade 分数 / fallback 率 / react 触发率 / 延迟持久化到 DB（新增 `models/metric.py`），为 ReAct vs quick path 效果对比与灰度决策提供数据
  2. 开关开启状态下跑一轮评估集，观察 20 case 的升级触发与答案质量（注意 token 成本）

---

### Session 2026-09-03（P1-1 检索能力 Tool 化）

- **目标**：完成 P1-1 — 把 retrieve/rerank/keyword/search 封装为标准 LangChain Tool，为 P1-2 ReAct agent 自主调用打基础；现有 LangGraph 静态图（quick path）保持不动并继续作为线上主链路
- **完成任务**：
  - [P1-1] retrieve/rerank/keyword/search 改造成 LangGraph Tool — 改动文件：
    - `app/agent/tools/_common.py`（新增）：Tool 版共用输出层，`format_chunks_for_llm()` 把 chunk list 序列化为紧凑 JSON（index/chunk_id/document_id/score/text 截断 300 字符），`format_tool_error()` 统一错误返回（Tool 不抛异常，让 agent 看到错误自纠），`pick_score()` 按 rerank_score>final_score>score>keyword_score>bm25_score 优先级取分
    - `app/agent/tools/keyword_tool.py`（新增）：`keyword_search_tool()` 纯函数（复用 `hybrid_retrieval.keyword_recall`，出口切 `[:top_k]` 保证工具语义）+ `make_keyword_search_tool()` 工厂（`keyword_search`，BM25 词法检索，适合精确术语/编号/错误码）
    - `app/agent/tools/vector_tool.py`：追加 `make_vector_search_tool()`（`vector_search`，纯语义检索，混合检索无结果时兜底）；原 `vector_search_tool()` 纯函数一行不动
    - `app/agent/tools/hybrid_tool.py`：追加 `make_hybrid_search_tool(user_id, rag_trace=None)`（`hybrid_search`，向量+BM25 融合，ReAct 首选工具，rag_trace 可选透传延续 timing/cache_hit 记录）；原 `hybrid_search_tool()` 纯函数一行不动
    - `app/agent/tools/rerank_tool.py`：追加 `make_rerank_tool()`（`rerank`，cross-encoder 精排）+ `_parse_docs_arg()` 解析 LLM 传入的 docs JSON（兼容 `{"count":N,"chunks":[...]}` 包装格式与裸数组，仅保留含 text 的 dict）；原 `rerank_tool()` 纯函数一行不动
    - `app/agent/tools/__init__.py`（原为空）：re-export 4 个纯函数 + 4 个工厂，新增 `build_retrieval_tools(user_id, *, rag_trace=None)` 一次性构造工具集，返回顺序即推荐优先级 hybrid > vector > keyword > rerank
    - `app/services/hybrid_retrieval.py`：新增 public `keyword_recall(query, top_k, *, user_id)` 入口包装私有 `_keyword_recall`（最小改动，hybrid 内部融合流程仍直接调 `_keyword_recall`，召回池放大逻辑不变）
- **关键决策**：
  - **双轨并存，quick path 零改动**：纯函数（返回 dict list）供 graph 节点继续直接调用；StructuredTool 工厂（返回紧凑 JSON 字符串）供 P1-2 ReAct 的 ToolMessage 消费。两者委托同一底层实现（retrieval_service / hybrid_retrieval / RerankService），不存在逻辑分叉；graph.py / state.py / prompts.py / 节点全部未动
  - **user_id 闭包绑定，绝不进 tool schema**：租户隔离参数由服务端（chat 入口）在工厂处注入，LLM 可见的 args 只有 query/top_k/top_n/docs，冒烟断言 schema 无 user_id 泄漏，防止 agent 被诱导跨租户检索
  - **Tool 不抛异常**：空 query / 检索无结果 / docs JSON 解析失败 / 模型异常均返回 `{"error": ...}` JSON 字符串，让 ReAct agent 能看到错误并自纠（换工具/改 query）
  - **rerank 工具无需 user_id**：cross-encoder 是本地模型推理、不访问向量库，租户隔离已在上游检索环节完成；且 4 个工具均不调用 LLM（rerank 非 LLM），P0-6 token 统计无需任何改动
  - **keyword 独立工具出口切 [:top_k]**：底层 `_keyword_recall` 按 RECALL_MULTIPLIER=2 放大召回池是给融合阶段用的，独立工具尊重 top_k 语义；切片只在纯函数出口，hybrid 融合路径不受影响
  - **无新增依赖**：`langchain-core`（StructuredTool）已在 requirements.txt
- **验证**：
  - 冒烟测试（临时脚本，跑完已删）：4 工具注册成功（hybrid_search/vector_search/keyword_search/rerank）；args schema 均无 user_id；hybrid/vector/keyword 主路径返回正确 JSON；rerank 可直接吃 hybrid_search 返回 JSON 模拟多工具串联，裸数组也兼容；空 query/非法 docs/空 docs 均返回 error JSON 不抛异常；**user_id=999 检索 user_id=1 数据返回无结果（租户隔离在 Tool 层生效）**；user_id=None 未登录/评估场景兼容
  - 评估回归（`scripts/evaluate_agent_day18.py`，.venv 环境，需 `PYTHONPATH=.`）：20 case 全通过
    - avg_answer_correctness 0.9（持平基线）
    - avg_retrieval_recall@8 0.9（持平基线）
    - avg_rerank_recall@5 0.8（持平基线）
    - grounding 20/20 passed，无误杀
- **未完成/遗留**：
  - Tool 层目前只有冒烟验证，尚无 ReAct 调用方；P1-2 新增 `react_agent.py` 时通过 `build_retrieval_tools(user_id)` 接入，并决定 quick path / ReAct 的路由策略
  - Tool 输出 text 截断 300 字符为固定值，P1-2 实际 ReAct 调试后如发现上下文不足再调
- **下一步建议**：
  1. P1-2：新增 `app/agent/react_agent.py`，用 langgraph prebuilt `create_react_agent`（langgraph-prebuilt 已在依赖）绑定 `build_retrieval_tools()`，保留现有图为 quick path，二者并存
  2. P1-2 需要决策：quick path 与 ReAct 的分流方式（按 route？按置信度？灰度开关？），开工前与用户确认

---

### Session 2026-09-03（P0-6 token 消耗统计）

- **目标**：完成 P0-6 — 在 rag_trace 中记录每轮/每节点 token 消耗，前端可展示 session 总 token 与各环节 token；P0 阶段收尾
- **完成任务**：
  - [P0-6] token 消耗统计 — 改动文件：
    - `app/services/llm_service.py`：新增 `generate_answer_with_usage()` 返回 `(text, usage_dict)`，从 OpenAI 兼容 `response.usage` 取 prompt/completion/total tokens；原 `generate_answer()` 改为委托以保持向后兼容
    - `app/schemas/rag_trace.py`：新增 `record_token_usage(trace, node, prompt_tokens, completion_tokens, latency_ms, source)` 写 `by_node` + 累加 `total`；`create_rag_trace`/`ensure_rag_trace` 初始化 `token_usage` 骨架（model/total/by_node）；按 user 要求**不计算 cost**
    - `app/core/config.py`：无新增配置（cost 移除后无需 model 价目）
    - `app/agent/nodes/classify_node.py`、`rewrite_node.py`、`answer_node.py`（chat+kb_qa 两路）、`grounding_check_node.py`：改用 `generate_answer_with_usage`，调 `record_token_usage`；LLM 失败/规则兜底路径记 0 token + source 标记
    - `app/services/query_expansion_service.py`：`hyde_expand` 同上
    - `app/agent/debug.py`：`build_agent_debug_summary` 暴露 `token_total`
    - `app/services/chat_session_service.py`：新增 `get_session_usage(session_id, user_id)` 聚合该 session 所有 assistant 消息 `rag_trace.token_usage.total`（O(n) 遍历）
    - `app/services/agent_memory_service.py`：re-export `get_session_usage`
    - `app/routers/chat.py`：新增 `GET /chat/agent/sessions/{session_id}/usage`
    - `frontend/src/api/chat.js`：新增 `getSessionUsage(sessionId)`
    - `frontend/src/pages/Chat.jsx`：TracePanel 新增 "Session total" + "Token usage (this turn)" 区块（total + by_node 各环节 token/latency/source）；loadSession 拉取 session 用量；done 事件后刷新
- **关键决策**：
  - token 统计放 `rag_trace.token_usage` 而非 AgentState 顶层字段：rag_trace 经 `save_turn` 自动持久化到 `chat_messages.rag_trace` JSON 列，前端 TracePanel 已渲染 rag_trace，零 DB schema 变更；放 state 顶层则需再串到 rag_trace 才能持久化/展示，多此一举
  - 按 user 要求只统计 token 不算/不输出成本：原 handoff 提的 `cost_usd` 移除，`token_usage.total` 仅 prompt/completion/total
  - session 级聚合用 Python O(n) 遍历而非 SQL JSON_EXTRACT：session 消息量小可接受，避免 SQLite JSON 函数版本依赖；量大再建冗余表
  - Langfuse spans/generations 细化留到 P1：避免 P0-6 范围膨胀
  - 流式 `stream_answer` 不动：agent 链路实际用非流式 `generate_answer`（graph 跑完才切片假流式），token 完整可取
- **环境**：用户确认运行环境为项目 `.venv`（`C:\Users\HP\Desktop\项目\rag-knowledge-base\.venv\Scripts\python.exe`），非 conda base；后续脚本/评估均用 .venv
- **验证**：
  - 全模块 import 通过（.venv python）
  - 评估回归（`scripts/evaluate_agent_day18.py`，.venv 环境）：20 case 全通过
    - avg_answer_correctness 0.9（持平基线）
    - avg_retrieval_recall@8 0.9（持平基线）
    - avg_rerank_recall 0.8（持平基线）
    - need_fallback 0（grounding 无误杀）
  - token_usage 写入由各 LLM 节点 record_token_usage 调用 + 评估跑通无异常间接验证；实际 token 数值需前端实测
- **未完成/遗留**：
  - Langfuse 上报细化为 spans/generations（含 token usage）留到 P1
  - token_usage 实际数值的端到端展示验证需用户启动前后端在前端 TracePanel 实测
- **下一步建议**：
  1. P0 阶段已全部完成，进入 P1（ReAct agent 改造）
  2. P1-1 起步：把 retrieve/rerank/keyword/search 改造成 LangGraph Tool

---

### Session 2026-09-02（P0-5 Langfuse 接入）

- **目标**：完成 P0-5 — 接入 Langfuse Cloud Hobby，把 agent 调用标准化上报为顶层 Trace；采用"代码就绪 + 默认关闭"渐进式方案，开关 `LANGFUSE_ENABLED=False` 时零 SDK 初始化、零网络调用，不阻塞主流程
- **完成任务**：
  - [P0-5] Langfuse 接入 — 改动文件：
    - `requirements.txt`：新增 `langfuse==4.15.1`（v4 SDK，OpenTelemetry-based，API 从 `Langfuse()` 改为 `get_client()`）
    - `app/core/config.py`：新增 4 个配置项 `LANGFUSE_ENABLED`(默认 False)/`LANGFUSE_HOST`(默认 `https://cloud.langfuse.com`)/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`
    - `app/services/langfuse_service.py`（新增）：
      - `_get_client()` 懒加载单例，开关关闭或缺 keys 时返回 None
      - `report_agent_trace(...)` 封装一次顶层 Trace 上报（input=question/output=final_answer/metadata=route+cache+grounding+timing/tags=user_id+session_id+route+cache-hit+fallback）
      - 内部全 try/except 兜底，任何 Langfuse 错误只 log warning 不影响主流程
      - 不上报原文 chunk 全文（metadata 只放 timing_ms 和 chunks 计数，为 PII 脱敏预留）
      - `flush()` 主动 flush，长驻进程可不调
    - `app/services/agent_chat_service.py`：try 末尾成功路径 + except 失败路径各调一次 `report_agent_trace`
    - `app/services/agent_stream_service.py`：trace SSE 事件前成功路径 + except 失败路径各调一次（except 路径加 `locals()` 兜底防 NameError）
- **关键决策**：
  - 部署形态选 Langfuse Cloud Hobby 而非本地自建：自建需常驻 ClickHouse(~3-4GB)+Postgres+Redis 共 ~6-8GB，与本地开发机已有的 uvicorn+Vite+ChromaDB+embedding 叠加易卡；Hobby 50k units/月对个人项目绰绰有余
  - 数据治理考量：trace 中带 query/检索原文，未来 P1 PII 脱敏阶段会再加 masking；当前个人学习项目数据未涉真实租户，不构成冲突
  - 渐进式开关：`LANGFUSE_ENABLED=False` 默认关闭，代码合入主干不影响现有评估基线；用户拿到 Cloud keys 后填 `.env` 并开关切 True 即可激活，零代码改动
  - 上报粒度 P0-5 只做顶层 Trace：P0-6 加 token/cost 后再细化为 spans/generations
  - SDK v4 vs v3：v4 是 OpenTelemetry-based，host 环境变量名从 `LANGFUSE_HOST` 改为 `LANGFUSE_BASE_URL`；service 层显式注入 env 避免依赖 .env 自动加载顺序
- **环境配置**（用户拿到 keys 后填 .env）：
  ```
  LANGFUSE_ENABLED=true
  LANGFUSE_PUBLIC_KEY=pk-lf-xxx
  LANGFUSE_SECRET_KEY=sk-lf-xxx
  LANGFUSE_HOST=https://cloud.langfuse.com
  ```
- **验证**：
  - 后端启动正常：`Application startup complete`，import 链路通过（langfuse_service 被两个 service 顺利引入）
  - no-op 路径 smoke test：`LANGFUSE_ENABLED=False` 时 `_get_client()` 返回 None，`report_agent_trace` 静默返回，无 SDK 初始化/网络调用
  - 评估回归（`scripts/evaluate_agent_day18.py`，开关默认关闭）：20 case 全通过
    - avg_answer_correctness 0.9（持平基线）
    - avg_retrieval_recall@8 0.9（持平基线）
    - avg_rerank_recall@5 0.8（持平基线）
    - grounding 20/20 passed，0/20 grounding_failed fallback
- **未完成/遗留**：
  - Langfuse 端到端实际验证（开关切 True 后能在 Cloud UI 看到 trace）需用户注册 cloud.langfuse.com 拿 keys 后填 .env 才能验证，本 session 仅代码就绪
  - token/cost 统计留到 P0-6（state 加 tokens_used/cost_usd/latency_ms 字段并填充，然后 spans 化上报）
- **下一步建议**：
  1. P0-6（token/cost 统计）→ P0 阶段收尾
  2. P0 完成后进入 P1（ReAct agent 改造）

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
