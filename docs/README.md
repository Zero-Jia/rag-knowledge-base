# RAG 知识库 - 开发文档

本目录是项目的**长期记忆库**，用于解决跨开发 session 上下文丢失问题。

## 📖 文档使用规则（给 Trae Code Agent）

每次新开 session 开发前，**必须按以下顺序阅读**：

1. **`05-agent-handoff.md`** ← 第一个读，快速了解当前状态与下一步
2. `00-overview.md` — 项目总览与目标
3. `03-task-backlog.md` — 查看所有任务及当前状态，找到 `todo` 的任务
4. `04-progress-log.md` — 了解最近几个 session 做了什么，避免重复或冲突
5. `06-conventions.md` — 开发规范，确保风格一致
6. 如需背景：`01-gap-analysis.md` + `02-roadmap.md`

## 📝 开发结束规则

每个 session 开发完成后，**必须更新**：

- `03-task-backlog.md`：把完成任务的状态从 `todo` → `doing` → `done`，并填写实际改动文件
- `04-progress-log.md`：追加一条 session 记录（模板见文件内）
- `05-agent-handoff.md`：更新"下一步建议"段落

## ⚠️ 重要

- **不要**在不读 `03-task-backlog.md` 的情况下开始写代码
- **不要**删除已 `done` 的任务记录，只更新状态
- **不要**修改 `00-overview.md` 除非项目目标发生重大变化

## 📁 文件清单

| 文件 | 作用 |
|---|---|
| `README.md` | 本文件，文档使用说明 |
| `00-overview.md` | 项目总览：当前状态 + 目标状态 |
| `01-gap-analysis.md` | 与企业级 Agentic RAG 的差距分析 |
| `02-roadmap.md` | 开发路线图：P0/P1/P2/P3 分阶段 |
| `03-task-backlog.md` | 任务清单（核心）：每个任务带状态 |
| `04-progress-log.md` | 进度日志：按 session 记录 |
| `05-agent-handoff.md` | Agent 交接说明（入口文件） |
| `06-conventions.md` | 开发约定：命名、提交、测试、目录规范 |
