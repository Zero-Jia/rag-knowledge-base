import re
from typing import Dict, List

from rank_bm25 import BM25Okapi


def tokenize(text: str) -> List[str]:
    """
    对文本做一个非常轻量的分词：
    - 全部转小写
    - 只保留 \w+ 形式的 token
    """
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


def keyword_score(text: str, query: str) -> float:
    """
    保留一个兼容旧逻辑的简单关键词计分函数。
    这样如果项目里其他地方还在调用 keyword_score，不会直接报错。
    """
    query_tokens = tokenize(query)
    text_lower = text.lower() if text else ""

    score = 0.0
    for token in query_tokens:
        if token in text_lower:
            score += 1.0

    return score


def bm25_rerank(query: str, chunks: List[Dict]) -> List[Dict]:
    """
    使用 BM25 对已有候选 chunks 进行词法打分。

    参数：
    - query: 用户问题
    - chunks: 候选 chunk 列表，每个元素至少包含:
        {
            "text": "...",
            "document_id": ...,
            "score": ...   # 向量检索阶段返回的分数/距离
        }

    返回：
    - 在每个 chunk 上新增 keyword_score 字段（这里实际就是 BM25 分数）
    """
    if not chunks:
        return []

    corpus = [chunk.get("text", "") for chunk in chunks]
    tokenized_corpus = [tokenize(text) for text in corpus]
    query_tokens = tokenize(query)

    # 防止空语料报错
    if not query_tokens or all(len(doc_tokens) == 0 for doc_tokens in tokenized_corpus):
        enriched_chunks = []
        for chunk in chunks:
            item = dict(chunk)
            item["keyword_score"] = 0.0
            enriched_chunks.append(item)
        return enriched_chunks

    bm25 = BM25Okapi(tokenized_corpus)
    bm25_scores = bm25.get_scores(query_tokens)

    enriched_chunks: List[Dict] = []
    for chunk, score in zip(chunks, bm25_scores):
        item = dict(chunk)
        item["keyword_score"] = float(score)
        enriched_chunks.append(item)

    return enriched_chunks