import json
import os
import sys
import requests
import time
import random
from typing import Any, Dict, List, Optional, Tuple

BASE_URL = os.getenv("EVAL_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("EVAL_TOKEN", "").strip()
TOP_K = int(os.getenv("EVAL_TOP_K", "5"))

# ✅ 禁用 unified /search（带 retrieval_mode）
UNIFIED_SEARCH_ENDPOINT = None

# ✅ 按你 Swagger 的真实路径填写（注意末尾 /）
MODE_TO_ENDPOINT_FALLBACK = {
    "semantic": "/search/",
    "hybrid": "/search/hybrid/",
    "rerank": "/search/rerank/",
}

QUESTIONS_PATH = os.getenv("EVAL_QUESTIONS", "evaluation/questions.json")


def build_headers() -> Dict[str, str]:
    """
    ✅ 方案2核心：只在 TOKEN 存在时才发送 Authorization
    避免发送空头：Authorization: ""
    """
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    return headers


def _extract_items(resp_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    兼容多种返回结构，尽量把检索结果 list 抽出来。
    你常见的可能是：
      - {"data": {"items": [...]}}
      - {"data": {"results": [...]}}
      - {"results": [...]}
      - {"items": [...]}
      - {"query": "...", "results": [...]}  # 你的 search/hybrid 和 search/rerank 就是这种
    """
    if not isinstance(resp_json, dict):
        return []

    # ✅ 你项目的 router 返回：{"query":..., "results":[...]}
    v = resp_json.get("results")
    if isinstance(v, list):
        return v

    # APIResponse 风格
    data = resp_json.get("data")
    if isinstance(data, dict):
        for key in ("items", "results"):
            vv = data.get(key)
            if isinstance(vv, list):
                return vv

    # 直接顶层
    for key in ("items", "results"):
        vv = resp_json.get(key)
        if isinstance(vv, list):
            return vv

    return []


def _post_json(url: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    # ✅ 避免触发限流：每次请求都稍微睡一下（基础节流）
    time.sleep(0.35 + random.random() * 0.15)  # 0.35~0.50s

    # ✅ 429 自动重试（指数退避）
    max_retries = 6
    backoff = 0.6

    for attempt in range(max_retries):
        r = requests.post(url, headers=build_headers(), json=payload, timeout=60)

        trace_id = r.headers.get("x-trace-id")
        raw_text = r.text

        try:
            j = r.json()
        except Exception:
            j = {"_raw": raw_text}

        if r.status_code == 429:
            # 等一等再试
            sleep_s = backoff * (2 ** attempt)
            print(f"[rate_limit] 429 on {url} trace_id={trace_id} -> sleep {sleep_s:.2f}s then retry")
            time.sleep(sleep_s)
            continue

        return r.status_code, j

    # 超过重试次数仍是 429
    return 429, {"detail": "Too many requests (retry exhausted)"}


def _try_unified_search(mode: str, question: str) -> Optional[List[Dict[str, Any]]]:
    """
    尝试调用统一 /search 并携带 retrieval_mode（当前已禁用）
    """
    if not UNIFIED_SEARCH_ENDPOINT:
        return None

    url = f"{BASE_URL}{UNIFIED_SEARCH_ENDPOINT}"
    payload = {"query": question, "top_k": TOP_K, "retrieval_mode": mode}
    status, j = _post_json(url, payload)

    if status == 404:
        return None
    if status >= 400:
        raise RuntimeError(f"Unified search failed: status={status}, resp={j}")

    return _extract_items(j)


def _try_fallback_endpoint(mode: str, question: str) -> List[Dict[str, Any]]:
    endpoint = MODE_TO_ENDPOINT_FALLBACK.get(mode)
    if not endpoint:
        raise RuntimeError(f"No fallback endpoint configured for mode={mode}")

    url = f"{BASE_URL}{endpoint}"
    payload = {"query": question, "top_k": TOP_K}

    status, j = _post_json(url, payload)
    if status >= 400:
        raise RuntimeError(f"Fallback endpoint failed: mode={mode}, status={status}, resp={j}")

    return _extract_items(j)


def search(mode: str, question: str) -> List[Dict[str, Any]]:
    items = _try_unified_search(mode, question)
    if items is not None:
        return items
    return _try_fallback_endpoint(mode, question)


def evaluate(mode: str, questions: List[Dict[str, str]]) -> Tuple[int, int]:
    hit_count = 0

    for idx, q in enumerate(questions, start=1):
        question = q["question"]
        expected = q["expected_keyword"].lower().strip()

        try:
            items = search(mode, question)
        except Exception as e:
            print(f"\n[{mode}] ERROR on question #{idx}: {question}")
            print(f"[{mode}] Exception: {e}\n")
            raise  # 你也可以改成 continue

        hit = False
        for it in items:
            text = str(it.get("text", "")).lower()
            if expected in text:
                hit = True
                break

        if hit:
            hit_count += 1

    return hit_count, len(questions)


def main():
    if not os.path.exists(QUESTIONS_PATH):
        print(f"[ERROR] questions file not found: {QUESTIONS_PATH}")
        sys.exit(1)

    # ✅ 小提示：一眼看出脚本有没有拿到 token
    print(f"[eval] token_len={len(TOKEN)}")

    if not TOKEN:
        print("[ERROR] Missing token. Please set EVAL_TOKEN env var.")
        print("Example:")
        print('  export EVAL_TOKEN="xxx"')
        sys.exit(1)

    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions = json.load(f)

    for mode in ("semantic", "hybrid", "rerank"):
        hit, total = evaluate(mode, questions)
        print(f"{mode} Hit@{TOP_K}: {hit}/{total}")


if __name__ == "__main__":
    main()