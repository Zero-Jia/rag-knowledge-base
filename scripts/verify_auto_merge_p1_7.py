"""P1-7 验证脚本：auto_merge（Small-to-Big）在 agent 链路的实际行为验证。

验证目标（只读验证，不改任何业务代码）：
  Part A 数据层：向量库/DB 中层级 chunk 覆盖情况（merge 的前提条件）
  Part B 检索层：hybrid_search_tool 是否实际返回合并后的父块（零 LLM）
  Part C rerank 层：父块经 cross-encoder 精排后是否存活（零 LLM，本地推理）
  Part D 端到端：quick path 全图跑通后 citations 是否正确指向父块（少量 LLM）

用法：
  .venv\\Scripts\\python.exe scripts\\verify_auto_merge_p1_7.py
可选环境变量：
  E2E_CASE_IDS=3,4   指定端到端验证的 question id（默认自动挑 merge 触发的前 2 个）
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

warnings.filterwarnings("ignore", category=UserWarning, module="jieba")

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.parent_chunk import ParentChunk  # noqa: E402
from app.agent.tools.hybrid_tool import hybrid_search_tool  # noqa: E402
from app.agent.tools.rerank_tool import rerank_tool  # noqa: E402

TOP_K = int(os.getenv("VERIFY_TOP_K", "8"))
RERANK_TOP_N = int(os.getenv("VERIFY_RERANK_TOP_N", "5"))
USER_ID = 1


def load_questions() -> List[Dict[str, Any]]:
    path = Path("evaluation/questions.json")
    with open(path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    return [q for q in questions if q.get("type") == "in_scope" and 1 <= int(q.get("id", 0)) <= 20]


# ---------------------------------------------------------------------------
# Part A：数据层
# ---------------------------------------------------------------------------

def part_a_data_layer() -> Dict[str, Any]:
    print("\n===== Part A: 数据层（ParentChunk 表 + 向量库层级覆盖） =====")
    db = SessionLocal()
    try:
        rows = db.query(ParentChunk).all()
        level_counter = Counter(r.chunk_level for r in rows)
        print(f"ParentChunk 表总行数: {len(rows)}")
        for lv in sorted(level_counter):
            print(f"  level={lv}: {level_counter[lv]} 条")
        sample = rows[0] if rows else None
        if sample:
            print(
                f"样例: chunk_id={sample.chunk_id} level={sample.chunk_level} "
                f"text_len={len(sample.text or '')}"
            )
        return {
            "parent_chunk_rows": len(rows),
            "level_distribution": dict(level_counter),
            "has_hierarchy_data": len(rows) > 0,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Part B：检索层
# ---------------------------------------------------------------------------

def part_b_retrieval(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    print("\n===== Part B: 检索层（hybrid_search_tool 实际返回是否含合并父块） =====")
    print(f"配置: AUTO_MERGE_ENABLED={settings.AUTO_MERGE_ENABLED} "
          f"MIN_CHILDREN={settings.AUTO_MERGE_MIN_CHILDREN} "
          f"PARENT_RATIO={settings.AUTO_MERGE_PARENT_RATIO} "
          f"MAX_PARENT_CHARS={settings.AUTO_MERGE_MAX_PARENT_CHARS}")

    merged_questions = []
    for q in questions:
        trace: Dict[str, Any] = {
            "original_query": q["question"],
            "retrieval_mode": "hybrid",
            "initial_chunks": [],
            "merged_chunks": [],
            "auto_merge_steps": [],
        }
        docs = hybrid_search_tool(
            question=q["question"], top_k=TOP_K, user_id=USER_ID, rag_trace=trace
        )
        merged_docs = [d for d in docs if d.get("auto_merged")]
        level_counter = Counter(d.get("chunk_level") for d in docs)
        parent_text_lens = [len(d.get("text") or "") for d in merged_docs]
        summary = trace.get("auto_merge_summary") or {}

        triggered = bool(merged_docs) or bool(summary.get("merged_count"))
        if triggered:
            merged_questions.append({"id": q["id"], "question": q["question"], "docs": docs})

        print(
            f"[q{q['id']:>2}] docs={len(docs)} merged={len(merged_docs)} "
            f"levels={dict(level_counter)} "
            f"parent_text_len={max(parent_text_lens) if parent_text_lens else '-'} "
            f"trace_merged_count={summary.get('merged_count', 0)}"
        )

    print(f"\nmerge 触发率: {len(merged_questions)}/{len(questions)} 个问题触发过合并")
    return merged_questions


# ---------------------------------------------------------------------------
# Part C：rerank 层
# ---------------------------------------------------------------------------

def part_c_rerank(merged_questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    print("\n===== Part C: rerank 层（父块经 cross-encoder 精排后是否存活） =====")
    if not merged_questions:
        print("无 merge 触发样本，跳过")
        return {"samples": 0, "parent_survived": 0, "parent_dropped": 0}

    survived = dropped = 0
    for item in merged_questions:
        docs: List[Dict[str, Any]] = item["docs"]
        parent_ids_before = {d["chunk_id"] for d in docs if d.get("auto_merged")}
        reranked = rerank_tool(question=item["question"], docs=docs, top_n=RERANK_TOP_N)
        parent_ids_after = {d["chunk_id"] for d in reranked if d.get("auto_merged")}

        hit = parent_ids_before & parent_ids_after
        survived += len(hit)
        dropped += len(parent_ids_before - hit)

        rr_scores = [
            f"{'P' if d.get('auto_merged') else 'c'}:{round(float(d.get('rerank_score') or 0), 3)}"
            for d in reranked
        ]
        print(
            f"[q{item['id']:>2}] 父块精排前={len(parent_ids_before)} "
            f"精排后存活={len(hit)} -> {sorted(parent_ids_after) if parent_ids_after else '无'} | "
            f"{' '.join(rr_scores)}"
        )

    print(f"\n父块精排存活: {survived}，被挤出: {dropped}")
    return {"samples": len(merged_questions), "parent_survived": survived, "parent_dropped": dropped}


# ---------------------------------------------------------------------------
# Part D：端到端（少量 LLM）
# ---------------------------------------------------------------------------

def part_d_e2e(pick_ids: List[int]) -> List[Dict[str, Any]]:
    print("\n===== Part D: 端到端（quick path 全图 + citations 指向验证） =====")
    import app.agent.nodes.answer_node as answer_node
    import app.agent.nodes.cache_node as cache_node
    import app.agent.tools.cache_tool as cache_tool
    from app.agent.graph import agent_graph

    # 评测模式：禁缓存（与 evaluate_agent_day18.py 同款 patch）
    cache_tool.lookup_exact_cache = lambda **kwargs: None
    cache_tool.lookup_semantic_cache = lambda **kwargs: None
    cache_tool.save_agent_cache = lambda **kwargs: None
    cache_node.lookup_exact_cache = lambda **kwargs: None
    cache_node.lookup_semantic_cache = lambda **kwargs: None
    answer_node.save_agent_cache = lambda **kwargs: None

    questions = {int(q["id"]): q for q in load_questions()}
    results = []
    for qid in pick_ids:
        q = questions.get(qid)
        if not q:
            print(f"[q{qid}] 不在问题集中，跳过")
            continue

        state = {
            "question": q["question"],
            "session_id": f"verify-merge-{qid}",
            "chat_history": [],
            "debug_info": {
                "user_id": USER_ID,
                "top_k": TOP_K,
                "rerank_top_n": RERANK_TOP_N,
                "rerank_score_threshold": 0.1,
                "min_reranked_docs": 1,
            },
        }
        result = agent_graph.invoke(state)

        reranked_docs = result.get("reranked_docs", [])
        parent_in_context = [d for d in reranked_docs if d.get("auto_merged")]
        citations = result.get("citations", [])
        rag_trace = result.get("rag_trace", {})
        grade_metrics = (rag_trace.get("grade_documents") or {}).get("metrics") or {}
        e2e = {
            "id": qid,
            "question": q["question"],
            "context_parent_count": len(parent_in_context),
            "context_parent_chunk_ids": [d.get("chunk_id") for d in parent_in_context],
            "context_parent_text_lens": [len(d.get("text") or "") for d in parent_in_context],
            "citation_chunk_ids": [c.get("chunk_id") for c in citations],
            "citation_hits_parent": [
                c.get("chunk_id") for c in citations
                if c.get("chunk_id") in {d.get("chunk_id") for d in parent_in_context}
            ],
            "grade_auto_merged_count": grade_metrics.get("auto_merged_count"),
            "grounding_passed": result.get("grounding_passed"),
            "need_fallback": result.get("need_fallback", False),
            "answer_preview": (result.get("final_answer") or "")[:100],
        }
        results.append(e2e)
        print(json.dumps(e2e, ensure_ascii=False, indent=2))
    return results


def main():
    print(f"AUTO_MERGE_ENABLED = {settings.AUTO_MERGE_ENABLED}")
    questions = load_questions()
    print(f"载入 {len(questions)} 个 in_scope 问题（user_id={USER_ID}, top_k={TOP_K}）")

    part_a_data_layer()
    merged_questions = part_b_retrieval(questions)
    part_c_rerank(merged_questions)

    e2e_ids_env = os.getenv("E2E_CASE_IDS", "").strip()
    if e2e_ids_env:
        pick_ids = [int(x) for x in e2e_ids_env.split(",") if x.strip()]
    else:
        pick_ids = [item["id"] for item in merged_questions[:2]] or [questions[0]["id"]]
    print(f"端到端验证 case: {pick_ids}")
    part_d_e2e(pick_ids)


if __name__ == "__main__":
    main()
