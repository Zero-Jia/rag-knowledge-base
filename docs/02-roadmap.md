# 开发路线图

按 ROI（投入产出比）排序，分四个阶段推进。

## P0：高价值快速落地（目标 2 周）

| 编号 | 任务 | 目标 |
|---|---|---|
| P0-1 | answer_node 引用溯源（inline citation + chunk_id 映射） | 答案可信度 |
| P0-2 | groundedness 校验：答案生成后 LLM 判断是否被证据支持，不通过则 fallback | 幻觉控制 |
| P0-3 | retrieve_node / vector_tool / hybrid_tool 加 `tenant_id`/`user_id` metadata filter | 租户隔离 |
| P0-4 | 文档上传时写入 `tenant_id`/`owner_id` metadata | 租户隔离配套 |
| P0-5 | 接入 Langfuse，标准化 trace 导出 | 可观测闭环 |
| P0-6 | state 增加 tokens_used / cost_usd / latency_ms 字段并填充 | 成本可观测 |

## P1：核心能力补齐（目标 1 个月）

| 编号 | 任务 | 目标 |
|---|---|---|
| P1-1 | retrieve/rerank/keyword/web_search 工具化，引入 ReAct Agent | Agent 自主性 |
| P1-2 | grade 分数 / fallback 率 / 延迟持久化到 DB | 在线监控 |
| P1-3 | 监控大盘 API（聚合指标查询） | 在线监控 |
| P1-4 | 文档索引切到 Celery + Redis broker | 可扩展索引 |
| P1-5 | 前端答案区加 👍/👎 按钮，写入 evaluation | 评估闭环 |
| P1-6 | agent 链路打通 auto_merge_service（Small-to-Big） | 召回质量 |

## P2：架构升级（目标 2 个月）

| 编号 | 任务 | 目标 |
|---|---|---|
| P2-1 | 向量库从 ChromaDB 迁到 Qdrant / Milvus / pgvector | 水平扩展 |
| P2-2 | 多知识库 namespace（collection per KB） | 多租户治理 |
| P2-3 | RBAC：admin / editor / viewer 角色与权限装饰器 | 权限控制 |
| P2-4 | CI 评估流水线（GitHub Actions / 本地脚本） | 质量保障 |
| P2-5 | 文档版本管理 + reindex 策略 | 数据治理 |
| P2-6 | 元数据过滤检索 API | 检索能力 |

## P3：长期增强

| 编号 | 任务 | 目标 |
|---|---|---|
| P3-1 | AB 实验框架（流量分桶对比 prompt/rerank 模型） | 持续优化 |
| P3-2 | Prompt Injection 检测 + PII 脱敏 | 安全 |
| P3-3 | 多模态检索（表格、图片、代码块） | 场景扩展 |
| P3-4 | 知识图谱增强检索 | 复杂推理 |
| P3-5 | 配置中心 + 特性开关 | 工程化 |

## 推进原则

- 每个 P 阶段必须全部 done 才进入下一阶段
- 允许跨阶段提前做依赖项（如 P1-1 工具化是 P0-1 引用溯源的前置，但 P0-1 可先在静态图内实现）
- 每完成一个任务必须更新 `03-task-backlog.md` 与 `04-progress-log.md`
- 任务粒度控制：单任务应在 1-2 个 session 内可完成
- 涉及破坏性改动（DB schema 变更、向量库迁移）需在 `04-progress-log.md` 写明 migration 路径
