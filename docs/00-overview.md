# 项目总览

## 基本信息

- **项目名称**：rag-knowledge-base
- **技术栈**：FastAPI + React + ChromaDB + Redis + LangGraph
- **项目路径**：`c:\Users\HP\Desktop\项目\rag-knowledge-base`
- **当前阶段**：已完成 Self-RAG / Corrective RAG 基础能力，向企业级 Agentic RAG 演进

## 当前已实现能力（基线）

### Agent 编排
- LangGraph 状态图：classify → cache → rewrite → retrieve → rerank → grade → expansion/fallback
- 证据门控（grade_documents_node）
- Query Expansion（HyDE / Step-back / 同义改写）
- Fallback / Refuse 机制
- 会话记忆与 trace/debug 信息

### 检索能力
- 向量检索、BM25 关键词检索、混合检索
- Cross-encoder rerank 重排
- 多轮追问改写

### 工程化
- JWT 鉴权、文档上传、异步索引
- 精确缓存 + 语义缓存
- SSE 流式输出
- Trace / Debug 信息（middleware/trace.py + rag_trace 字段）
- 离线评估脚本（evaluation/ + scripts/evaluate_*.py）
- 限流中间件（middleware/rate_limit.py）
- 父子分块模型（models/parent_chunk.py）+ auto_merge_service

## 目标状态（企业级 Agentic RAG）

- Agent 运行时自主决策（Tool Calling / ReAct）
- 引用溯源 + 幻觉检测
- 多租户隔离与权限控制
- 全链路可观测（Langfuse/LangSmith）
- 分布式任务队列与水平扩展
- 在线评估闭环（用户反馈回流）

## 关键文件索引

| 模块 | 入口文件 |
|---|---|
| Agent 图 | `app/agent/graph.py` |
| Agent 状态 | `app/agent/state.py` |
| Agent 节点 | `app/agent/nodes/*.py` |
| Agent 提示词 | `app/agent/prompts.py` |
| 检索工具 | `app/agent/tools/*.py` |
| 业务服务 | `app/services/*.py` |
| 数据模型 | `app/models/*.py` |
| API 路由 | `app/routers/*.py` |
| Schema | `app/schemas/*.py` |
| 中间件 | `app/middleware/*.py` |
| 配置 | `app/core/config.py` |
| 入口 | `app/main.py` |
| 评估 | `evaluation/` + `scripts/evaluate_*.py` |
| 前端 | `frontend/src/` |

## Agent 图结构（当前）

```text
classify
  -> cache
       -> rewrite
       -> retrieve_initial
       -> rerank_initial
       -> grade_documents
            -> answer
            -> query_expansion
                 -> retrieve_expanded
                 -> rerank_expanded
                 -> grade_documents
            -> fallback
```

## 现有 Agent State 字段（state.py）

```python
question, session_id, chat_history, route,
cache_hit, cached_answer,
rewritten_question,
retrieved_docs, reranked_docs,
initial_query, initial_retrieved_docs, initial_reranked_docs,
evidence_grade, grade_reason, grade_metrics,
need_query_expansion, expanded_queries, query_expansion_strategy,
expanded_retrieved_docs, combined_retrieved_docs, expanded_reranked_docs,
expansion_attempted, retrieval_attempts,
final_answer, rag_trace,
need_retry, need_fallback, fallback_reason,
debug_info
```
