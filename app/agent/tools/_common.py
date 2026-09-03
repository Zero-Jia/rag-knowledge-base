"""P1-1: LangChain Tool 版本的共用输出格式化。

Tool 版本面向 ReAct agent（P1-2）的 ToolMessage，返回紧凑 JSON 字符串；
graph quick path 继续使用各 xxx_tool 纯函数返回的 dict list，二者互不影响。
"""

import json
from typing import Any, Dict, List, Optional

# Tool 返回给 LLM 的单片段 text 最大长度（字符），避免 context 膨胀
DEFAULT_TEXT_LIMIT = 300

# 分数取值优先级：rerank 精排分 > 融合分 > 原始 score > 词法分
_SCORE_KEYS = ("rerank_score", "final_score", "score", "keyword_score", "bm25_score")


def _round_score(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def pick_score(chunk: Dict[str, Any]) -> Optional[float]:
    """从 chunk 中挑一个最能代表相关性的分数。"""
    for key in _SCORE_KEYS:
        value = chunk.get(key)
        if value is not None:
            return _round_score(value)
    return None


def format_chunks_for_llm(
    chunks: List[Dict[str, Any]],
    *,
    text_limit: int = DEFAULT_TEXT_LIMIT,
) -> str:
    """把检索/重排结果格式化为 LLM 友好的紧凑 JSON 字符串。"""
    items: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks or []):
        text = (chunk.get("text") or "").strip()
        text = text.replace("\r\n", " ").replace("\n", " ")
        if len(text) > text_limit:
            text = text[:text_limit] + "…"
        items.append(
            {
                "index": idx + 1,
                "chunk_id": chunk.get("chunk_id"),
                "document_id": chunk.get("document_id"),
                "score": pick_score(chunk),
                "text": text,
            }
        )

    return json.dumps({"count": len(items), "chunks": items}, ensure_ascii=False)


def format_tool_error(message: str) -> str:
    """Tool 执行出错时返回给 LLM 的提示（不抛异常，让 agent 看到错误后自纠）。"""
    return json.dumps({"error": message}, ensure_ascii=False)
