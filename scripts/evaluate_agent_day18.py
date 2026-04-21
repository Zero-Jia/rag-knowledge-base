import json
import os
import warnings
from pathlib import Path
from typing import Any, Dict, List

warnings.filterwarnings("ignore", category=UserWarning, module="jieba")

from app.agent.graph import agent_graph

# 只在评测脚本里禁用缓存，不改原项目
import app.agent.nodes.answer_node as answer_node
import app.agent.nodes.cache_node as cache_node
import app.agent.tools.cache_tool as cache_tool


EVAL_FILE = Path(os.getenv("EVAL_FILE", "evaluation/questions.json"))
EVAL_TOP_K = int(os.getenv("EVAL_TOP_K", "8"))
EVAL_RERANK_TOP_N = int(os.getenv("EVAL_RERANK_TOP_N", "5"))
EVAL_RERANK_SCORE_THRESHOLD = float(os.getenv("EVAL_RERANK_SCORE_THRESHOLD", "0.1"))


def disable_cache_for_evaluation():
    """
    只在本次评测运行期间禁用缓存，不修改原项目代码。

    注意：
    cache_node.py 使用了 `from cache_tool import lookup_exact_cache` 这种导入方式，
    所以只 patch cache_tool 不够，还必须 patch cache_node 中已绑定的函数名。
    """
    cache_tool.lookup_exact_cache = lambda **kwargs: None
    cache_tool.lookup_semantic_cache = lambda **kwargs: None
    cache_tool.save_agent_cache = lambda **kwargs: None

    cache_node.lookup_exact_cache = lambda **kwargs: None
    cache_node.lookup_semantic_cache = lambda **kwargs: None

    answer_node.save_agent_cache = lambda **kwargs: None


def load_questions() -> List[Dict[str, Any]]:
    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def select_first_20_in_scope(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    只选择前20个与知识库有关的问题：
    - type == in_scope
    - id 在 1~20
    """
    selected = []
    for q in questions:
        if q.get("type") == "in_scope" and 1 <= int(q.get("id", 0)) <= 20:
            selected.append(q)

    # 防御性排序，确保顺序稳定
    selected.sort(key=lambda x: int(x["id"]))
    return selected


def chunk_matches_gold(doc: Dict[str, Any], gold_chunks: List[Dict[str, Any]]) -> bool:
    """
    判断一个召回 chunk 是否命中 gold chunk

    当前版本：不依赖 document_id
    规则：
    1. 只看 text
    2. 如果 gold keywords 中至少命中 2 个，或者命中全部（当关键词少于2个）
       就认为这个 chunk 命中
    """
    text = (doc.get("text") or "").lower()

    for gold in gold_chunks:
        keywords = gold.get("keywords", [])
        if not keywords:
            continue

        matched = 0
        for kw in keywords:
            if kw.lower() in text:
                matched += 1

        required = min(2, len(keywords))
        if matched >= required:
            return True

    return False


def calc_precision_recall_at_k(
    retrieved_docs: List[Dict[str, Any]],
    gold_chunks: List[Dict[str, Any]],
    k: int = EVAL_TOP_K,
) -> Dict[str, Any]:
    """
    Precision@K = topK中相关chunk数 / K
    Recall@K = topK中找回的相关chunk数 / gold相关chunk总数
    """
    topk_docs = retrieved_docs[:k]

    if not gold_chunks:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "hit": 0.0,
            "mrr": 0.0,
            "matched_gold_count": 0,
            "gold_count": 0,
            "missed_gold_keywords": [],
            "matched_gold_keywords": [],
            "first_hit_rank": None,
        }

    hit_count = 0
    matched_gold_indices = set()
    first_hit_rank = None

    for rank, doc in enumerate(topk_docs, start=1):
        for idx, gold in enumerate(gold_chunks):
            if idx in matched_gold_indices:
                continue

            if chunk_matches_gold(doc, [gold]):
                hit_count += 1
                matched_gold_indices.add(idx)
                if first_hit_rank is None:
                    first_hit_rank = rank
                break

    precision = hit_count / k if k > 0 else 0.0
    recall = hit_count / len(gold_chunks) if gold_chunks else 0.0
    missed_gold_keywords = [
        gold.get("keywords", [])
        for idx, gold in enumerate(gold_chunks)
        if idx not in matched_gold_indices
    ]
    matched_gold_keywords = [
        gold.get("keywords", [])
        for idx, gold in enumerate(gold_chunks)
        if idx in matched_gold_indices
    ]

    return {
        "precision": precision,
        "recall": recall,
        "hit": 1.0 if hit_count > 0 else 0.0,
        "mrr": 1.0 / first_hit_rank if first_hit_rank else 0.0,
        "matched_gold_count": hit_count,
        "gold_count": len(gold_chunks),
        "missed_gold_keywords": missed_gold_keywords,
        "matched_gold_keywords": matched_gold_keywords,
        "first_hit_rank": first_hit_rank,
    }


def simple_answer_match(answer: str, gold_answer: str) -> bool:
    """
    一个较宽松的回答正确性近似判断：
    - 看 gold_answer 的关键短语是否部分出现在 answer 中
    """
    if not gold_answer.strip():
        return False

    answer_lower = answer.lower()
    tokens = [
        tok.strip()
        for tok in gold_answer.replace("，", ",").replace("。", ",").split(",")
        if tok.strip()
    ]
    if not tokens:
        return False

    hit = 0
    for tok in tokens:
        if tok.lower() in answer_lower:
            hit += 1

    return hit >= max(1, len(tokens) // 3)


def answer_matches_gold_keywords(answer: str, gold_chunks: List[Dict[str, Any]]) -> bool:
    """
    用 gold keywords 辅助判断答案正确性，避免中文生成答案没有逐字复述 gold_answer 时被误判。
    """
    answer_lower = (answer or "").lower()
    if not answer_lower or not gold_chunks:
        return False

    matched_gold_groups = 0
    for gold in gold_chunks:
        keywords = [kw for kw in gold.get("keywords", []) if kw]
        if not keywords:
            continue

        matched_keywords = sum(1 for kw in keywords if kw.lower() in answer_lower)
        required = min(2, len(keywords))
        if matched_keywords >= required:
            matched_gold_groups += 1

    required_groups = max(1, len(gold_chunks) // 2)
    return matched_gold_groups >= required_groups


def evaluate_one_case(item: Dict[str, Any]) -> Dict[str, Any]:
    question = item["question"]
    gold_answer = item.get("gold_answer", "")
    gold_chunks = item.get("gold_chunks", [])

    state = {
        "question": question,
        "session_id": f"eval-{item['id']}",
        "chat_history": [],
        "debug_info": {
            "user_id": 1,
            "top_k": EVAL_TOP_K,
            "rerank_top_n": EVAL_RERANK_TOP_N,
            # 评测阶段先降低阈值，避免 CrossEncoder 分数尺度导致误 fallback
            "rerank_score_threshold": EVAL_RERANK_SCORE_THRESHOLD,
            "min_reranked_docs": 1,
        },
    }

    result = agent_graph.invoke(state)

    retrieved_docs = result.get("retrieved_docs", [])
    reranked_docs = result.get("reranked_docs", [])
    answer = result.get("final_answer") or ""

    retrieval_metrics = calc_precision_recall_at_k(
        retrieved_docs=retrieved_docs,
        gold_chunks=gold_chunks,
        k=EVAL_TOP_K,
    )
    rerank_metrics = calc_precision_recall_at_k(
        retrieved_docs=reranked_docs,
        gold_chunks=gold_chunks,
        k=EVAL_RERANK_TOP_N,
    )

    answer_correct = simple_answer_match(answer, gold_answer) or answer_matches_gold_keywords(answer, gold_chunks)

    return {
        "id": item["id"],
        "question": question,
        "route": result.get("route"),
        "retrieval_precision_at_k": retrieval_metrics["precision"],
        "retrieval_recall_at_k": retrieval_metrics["recall"],
        "retrieval_hit_at_k": retrieval_metrics["hit"],
        "retrieval_mrr": retrieval_metrics["mrr"],
        "retrieval_first_hit_rank": retrieval_metrics["first_hit_rank"],
        "rerank_precision_at_n": rerank_metrics["precision"],
        "rerank_recall_at_n": rerank_metrics["recall"],
        "rerank_hit_at_n": rerank_metrics["hit"],
        "rerank_mrr": rerank_metrics["mrr"],
        "rerank_first_hit_rank": rerank_metrics["first_hit_rank"],
        "matched_gold_count": retrieval_metrics["matched_gold_count"],
        "gold_count": retrieval_metrics["gold_count"],
        "matched_gold_keywords": retrieval_metrics["matched_gold_keywords"],
        "missed_gold_keywords": retrieval_metrics["missed_gold_keywords"],
        "rerank_matched_gold_count": rerank_metrics["matched_gold_count"],
        "rerank_missed_gold_keywords": rerank_metrics["missed_gold_keywords"],
        "answer_correct": answer_correct,
        "retrieved_count": len(retrieved_docs),
        "reranked_count": len(reranked_docs),
        "retrieved_doc_ids": [doc.get("document_id") for doc in retrieved_docs],
        "reranked_doc_ids": [doc.get("document_id") for doc in reranked_docs],
        "answer_preview": answer[:120],
        "need_fallback": result.get("need_fallback", False),
        "fallback_reason": result.get("fallback_reason"),
        "debug_info": result.get("debug_info", {}),
    }


def main():
    disable_cache_for_evaluation()

    questions = load_questions()
    questions = select_first_20_in_scope(questions)

    results = []
    for item in questions:
        print(f"[eval] running id={item['id']} question={item['question']}")
        try:
            results.append(evaluate_one_case(item))
        except Exception as e:
            results.append(
                {
                    "id": item.get("id"),
                    "question": item.get("question"),
                    "error": str(e),
                }
            )

    valid_results = [r for r in results if "error" not in r]

    avg_precision = (
        sum(r["retrieval_precision_at_k"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_recall = (
        sum(r["retrieval_recall_at_k"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_hit = (
        sum(r["retrieval_hit_at_k"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_mrr = (
        sum(r["retrieval_mrr"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_matched_gold = (
        sum(r["matched_gold_count"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_rerank_precision = (
        sum(r["rerank_precision_at_n"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_rerank_recall = (
        sum(r["rerank_recall_at_n"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_rerank_hit = (
        sum(r["rerank_hit_at_n"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_rerank_mrr = (
        sum(r["rerank_mrr"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_rerank_matched_gold = (
        sum(r["rerank_matched_gold_count"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_answer_correctness = (
        sum(1 for r in valid_results if r["answer_correct"]) / len(valid_results)
        if valid_results else 0.0
    )

    summary = {
        "eval_file": str(EVAL_FILE),
        "evaluated_cases": len(valid_results),
        "top_k": EVAL_TOP_K,
        "rerank_top_n": EVAL_RERANK_TOP_N,
        "rerank_score_threshold": EVAL_RERANK_SCORE_THRESHOLD,
        "avg_retrieval_precision_at_k": avg_precision,
        "avg_retrieval_recall_at_k": avg_recall,
        "avg_retrieval_hit_at_k": avg_hit,
        "avg_retrieval_mrr": avg_mrr,
        "avg_retrieval_matched_gold_count": avg_matched_gold,
        "avg_rerank_precision_at_n": avg_rerank_precision,
        "avg_rerank_recall_at_n": avg_rerank_recall,
        "avg_rerank_hit_at_n": avg_rerank_hit,
        "avg_rerank_mrr": avg_rerank_mrr,
        "avg_rerank_matched_gold_count": avg_rerank_matched_gold,
        "avg_answer_correctness": avg_answer_correctness,
    }

    print(f"\n===== EVALUATION SUMMARY ({EVAL_FILE}) =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n===== PER-CASE RESULTS =====")
    for r in results:
        print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
