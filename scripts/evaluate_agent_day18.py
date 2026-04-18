import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.agent.graph import agent_graph

# 只在评测脚本里禁用缓存，不改原项目
import app.agent.tools.cache_tool as cache_tool


EVAL_FILE = Path("evaluation/questions.json")


def disable_cache_for_evaluation():
    """
    只在本次评测运行期间禁用缓存，不修改原项目代码。
    """
    cache_tool.lookup_exact_cache = lambda **kwargs: None
    cache_tool.lookup_semantic_cache = lambda **kwargs: None


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
    k: int = 5,
) -> Tuple[float, float]:
    """
    Precision@K = topK中相关chunk数 / K
    Recall@K = topK中找回的相关chunk数 / gold相关chunk总数
    """
    topk_docs = retrieved_docs[:k]

    if not gold_chunks:
        return 0.0, 0.0

    hit_count = 0
    matched_gold_indices = set()

    for doc in topk_docs:
        for idx, gold in enumerate(gold_chunks):
            if idx in matched_gold_indices:
                continue

            if chunk_matches_gold(doc, [gold]):
                hit_count += 1
                matched_gold_indices.add(idx)
                break

    precision = hit_count / k if k > 0 else 0.0
    recall = hit_count / len(gold_chunks) if gold_chunks else 0.0
    return precision, recall


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
            "top_k": 5,
            "rerank_top_n": 3,
            # 调高 fallback 阈值，避免乱答
            "rerank_score_threshold": 6.0,
            "min_reranked_docs": 1,
        },
    }

    result = agent_graph.invoke(state)

    retrieved_docs = result.get("retrieved_docs", [])
    answer = result.get("final_answer") or ""

    precision_at_5, recall_at_5 = calc_precision_recall_at_k(
        retrieved_docs=retrieved_docs,
        gold_chunks=gold_chunks,
        k=5,
    )

    answer_correct = simple_answer_match(answer, gold_answer)

    return {
        "id": item["id"],
        "question": question,
        "route": result.get("route"),
        "precision_at_5": precision_at_5,
        "recall_at_5": recall_at_5,
        "answer_correct": answer_correct,
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
        sum(r["precision_at_5"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_recall = (
        sum(r["recall_at_5"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )
    avg_answer_correctness = (
        sum(1 for r in valid_results if r["answer_correct"]) / len(valid_results)
        if valid_results else 0.0
    )

    summary = {
        "evaluated_cases": len(valid_results),
        "avg_precision_at_5": avg_precision,
        "avg_recall_at_5": avg_recall,
        "avg_answer_correctness": avg_answer_correctness,
    }

    print("\n===== EVALUATION SUMMARY (FIRST 20 IN-SCOPE QUESTIONS) =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n===== PER-CASE RESULTS =====")
    for r in results:
        print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()