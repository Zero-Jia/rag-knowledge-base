# 开发约定

## 目录结构

```
app/
  agent/
    nodes/       # LangGraph 节点（xxx_node.py）
    tools/       # Agent 可调用的工具（xxx_tool.py）
    graph.py     # 图编排
    state.py     # AgentState 定义
    prompts.py   # 提示词
  core/          # 配置（config.py）
  middleware/    # 中间件（rate_limit、trace）
  models/        # SQLAlchemy 数据模型
  routers/       # FastAPI 路由
  schemas/       # Pydantic 输入输出 schema
  services/      # 业务服务层
  database.py
  main.py
  security.py
  error_handlers.py
  exceptions.py
  logging_config.py
docs/            # 本目录：跨 session 记忆库
evaluation/      # 离线评估数据与脚本
frontend/        # React 前端
scripts/         # 评估/工具脚本
```

## 命名规范

- 文件：`snake_case.py`
- 类：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- Agent node 函数：`xxx_node`（如 `answer_node`）
- Agent tool 函数：`xxx_tool`（如 `vector_tool`）
- Service 类：`XxxService`（如 `RetrievalService`）
- Router 前缀：`/api/<resource>/`

## Agent State 字段命名

- 布尔标志：`need_xxx` / `is_xxx` / `has_xxx`
- 列表：`xxx_docs` / `xxx_queries`（复数）
- 中间结果：`initial_xxx` / `expanded_xxx`
- 最终结果：`final_xxx`
- trace/debug：`rag_trace` / `debug_info`

## 新增能力 checklist

- [ ] 在对应 service 实现核心逻辑
- [ ] 在 schema 定义输入输出
- [ ] 在 router 暴露 API（如需要）
- [ ] 在 `state.py` 增加必要字段（如涉及 agent）
- [ ] 在 `prompts.py` 调整提示词（如涉及 LLM）
- [ ] 更新 `03-task-backlog.md` 与 `04-progress-log.md`
- [ ] 跑一次评估脚本回归（`scripts/evaluate_agent_day18.py`）

## 测试

- 关键服务必须有单元测试（`tests/` 目录，目前未建，P1 阶段补齐）
- 评估脚本：`scripts/evaluate_*.py`，改 prompt / 检索策略后必跑
- 评估数据：`evaluation/questions.json` + `evaluation/questions_multi_gold.json`

## 提交规范（Commit Message）

- 格式：`<type>: <描述>`
- type ∈ `feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `perf`
- 示例：
  - `feat: answer_node 增加 inline citation 引用溯源`
  - `fix: retrieve_node 修复 tenant_id 未传递问题`
  - `docs: 更新 03-task-backlog P0-1 状态为 done`

## 依赖管理

- 新增依赖必须更新 `requirements.txt`
- 优先使用已存在依赖，避免引入功能重复的库
- 新增依赖需在 `04-progress-log.md` 说明用途

## 破坏性变更

- DB schema 变更：必须先写 migration 说明到 `04-progress-log.md`
- API 契约变更：默认向后兼容，新字段以可选形式加入
- graph 结构变更：P0 阶段禁止破坏现有 quick path
- 向量库 schema 变更：需提供 reindex 脚本

## 文档维护规则

- 每个 session 结束**必须**更新：
  - `03-task-backlog.md`：任务状态 + 实际改动文件
  - `04-progress-log.md`：顶部追加 session 记录
  - `05-agent-handoff.md`：当前状态 + 下一步建议
- **不要**删除已 `done` 的任务记录
- **不要**在不读 backlog 的情况下开始写代码
