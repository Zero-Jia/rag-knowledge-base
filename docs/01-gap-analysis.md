# 与企业级 Agentic RAG 的差距分析

## 1. Agent 自主性不足（最大差距）

- **现状**：`app/agent/graph.py` 是静态预编排，节点与边写死，循环次数固定（query_expansion 仅一轮）
- **差距**：缺少 Tool Calling / ReAct / Plan-Execute，LLM 不能运行时自主选择检索工具与调用次数
- **影响**：复杂多跳问题（对比、聚合、跨文档推理）能力弱

## 2. 缺少引用溯源与幻觉控制

- **现状**：`answer_node.py` 输出答案，`reranked_docs` 在 state 中但未做 inline citation
- **差距**：
  - 无 `[1][2]` 引用标注
  - 无 groundedness/faithfulness 校验
  - 前端无法跳回原文
- **影响**：答案可信度不足，无法商用

## 3. 数据治理与多租户缺失

- **现状**：ChromaDB 全局 collection，无 tenant_id filter
- **差距**：
  - 无租户隔离（用户 A 可能检索到用户 B 的文档）
  - 无 RBAC（只有基础 JWT 鉴权，无 admin/editor/viewer 角色）
  - 无知识库分库（所有文档堆在一个 collection）
  - 无文档版本管理
  - 无审计日志
- **影响**：无法支撑多用户/多团队场景，存在数据泄露风险

## 4. 可观测性是半成品

- **现状**：自研 `rag_trace` dict + `middleware/trace.py`
- **差距**：
  - 未接 OpenTelemetry / Langfuse / LangSmith
  - 无 token 成本统计（state 无 `tokens_used` / `cost_usd` / `latency_ms` 字段）
  - 无在线召回质量监控（grade 分数未持久化）
  - 无用户反馈回流
  - 无告警机制
- **影响**：线上问题难定位，效果难持续优化

## 5. 检索层深度工程化不足

- **现状**：`parent_chunk.py` 模型已建但未在 agent 链路用满；只支持 PDF/TXT
- **差距**：
  - 无 Small-to-Big 上下文组装（`auto_merge_service.py` 是否真在 agent 链路调用待确认）
  - 无多模态（表格、图片、Excel、代码块）
  - 无元数据过滤 API（`filter={"source":..., "date_gte":...}`）
  - 无 embedding 模型平滑迁移策略
- **影响**：召回质量有上限，扩展性差

## 6. 工程化与可扩展性弱

- **现状**：ChromaDB 单机持久化、BackgroundTasks 异步索引、.env 配置
- **差距**：
  - 无分布式向量库（Milvus / Qdrant / pgvector）
  - 无 Celery 任务队列
  - 无配置中心 / 特性开关
  - 无 AB 实验
  - 无 CI 评估流水线（`scripts/evaluate_*.py` 未在 PR 自动跑）
- **影响**：无法水平扩展，无法支撑高并发与团队协作

## 7. 安全细节

- **现状**：基础鉴权
- **差距**：
  - 无 Prompt Injection 防护（检索文档直接拼进 prompt）
  - 无 PII 脱敏（日志和 trace 可能泄漏用户敏感内容）
  - PDF 解析无沙箱
- **影响**：存在安全风险

## 差距优先级矩阵

| 维度 | 影响面 | 改造难度 | 优先级 |
|---|---|---|---|
| Agent 自主性 | 高 | 高 | P1 |
| 引用溯源 | 高 | 低 | **P0** |
| 多租户隔离 | 高 | 中 | **P0** |
| 可观测性 | 中 | 中 | **P0** |
| 检索深度 | 中 | 中 | P2 |
| 工程化 | 中 | 高 | P2 |
| 安全 | 中 | 中 | P3 |
