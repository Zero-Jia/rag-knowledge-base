import math
import re
from collections import Counter
from typing import Dict, Iterable, List, Sequence

try:
    import jieba
except Exception:  # pragma: no cover - optional runtime dependency
    jieba = None

try:
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover - optional runtime dependency
    BM25Okapi = None


_ASCII_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_+#.-]*|\d+(?:\.\d+)?")
_CJK_SPAN_RE = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_OR_CJK_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_+#.-]*|\d+(?:\.\d+)?|[\u4e00-\u9fff]+")

_QUERY_STOPWORDS = {
    "请",
    "介绍",
    "一下",
    "介绍一下",
    "讲讲",
    "说说",
    "解释",
    "说明",
    "概述",
    "什么",
    "什么是",
    "是",
    "的",
    "了",
    "吗",
    "呢",
    "在",
    "中",
    "和",
    "与",
    "或",
    "及",
    "以及",
    "这个",
    "那个",
    "它",
    "其",
    "为什么",
    "需要",
    "要",
    "怎么",
    "如何",
    "有哪些",
}


class _SimpleBM25:
    """
    Small fallback BM25 implementation.

    It is only used when rank_bm25 is unavailable, so keyword search remains
    testable in lightweight local environments.
    """

    def __init__(self, corpus: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75):
        self.corpus = [list(doc) for doc in corpus]
        self.k1 = k1
        self.b = b
        self.doc_freq: Counter[str] = Counter()
        self.term_freqs: List[Counter[str]] = []
        self.doc_lens: List[int] = []

        for doc in self.corpus:
            tf = Counter(doc)
            self.term_freqs.append(tf)
            self.doc_lens.append(len(doc))
            self.doc_freq.update(tf.keys())

        self.n_docs = len(self.corpus)
        self.avgdl = sum(self.doc_lens) / self.n_docs if self.n_docs else 0.0

    def get_scores(self, query_tokens: Sequence[str]) -> List[float]:
        if not self.corpus or not query_tokens or self.avgdl <= 0:
            return [0.0 for _ in self.corpus]

        scores: List[float] = []
        unique_query_terms = set(query_tokens)
        for tf, dl in zip(self.term_freqs, self.doc_lens):
            score = 0.0
            for term in unique_query_terms:
                freq = tf.get(term, 0)
                if freq <= 0:
                    continue
                df = self.doc_freq.get(term, 0)
                idf = math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))
                denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                score += idf * (freq * (self.k1 + 1)) / denom
            scores.append(float(score))
        return scores


def _normalize_text(text: str) -> str:
    """
    基础清洗：
    - 转小写
    - 去掉多余空白
    """
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _char_ngrams(span: str, min_n: int = 2, max_n: int = 4) -> Iterable[str]:
    span = span.strip()
    if not span:
        return []

    grams: List[str] = []
    max_n = min(max_n, len(span))
    for n in range(min_n, max_n + 1):
        for i in range(0, len(span) - n + 1):
            grams.append(span[i : i + n])
    if 1 <= len(span) <= 8:
        grams.append(span)
    return grams


def tokenize(text: str) -> List[str]:
    """
    中文 + 英文混合分词：
    1. 先用 jieba 对中文做分词
    2. 再对英文/数字保留
    3. 过滤空 token

    目标：
    - 比原来的 \\w+ 更适合中文 BM25
    - 对 "什么是RAG" / "BM25在RAG中起什么作用" 这类问题更友好
    """
    text = _normalize_text(text)
    if not text:
        return []

    tokens: List[str] = []

    if jieba is not None:
        raw_tokens = jieba.lcut(text)
        for tok in raw_tokens:
            tok = tok.strip().lower()
            if not tok:
                continue
            if re.fullmatch(r"[^\w\u4e00-\u9fff]+", tok):
                continue
            tokens.append(tok)
    else:
        for match in _ASCII_OR_CJK_RE.finditer(text):
            token = match.group(0).lower()
            if _CJK_SPAN_RE.fullmatch(token):
                tokens.extend(_char_ngrams(token))
            else:
                tokens.append(token)

    # 额外加入中文 ngram，弥补 jieba 对领域词和中英混排词切分不稳定的问题。
    for span in _CJK_SPAN_RE.findall(text):
        tokens.extend(_char_ngrams(span))

    # 保序去重，避免长中文片段的重复 ngram 过度放大词频。
    return list(dict.fromkeys(tokens))


def extract_focus_terms(query: str) -> List[str]:
    """
    Extract the actual subject terms from a query.

    For "请介绍一下RAG?" this returns ["rag"], not generic words like "介绍".
    These terms are used for exact-match boosts and diagnostics.
    """
    q = _normalize_text(query)
    if not q:
        return []

    subject_text = q
    for stopword in sorted(_QUERY_STOPWORDS, key=len, reverse=True):
        subject_text = subject_text.replace(stopword, " ")

    terms: List[str] = []
    for token in tokenize(subject_text):
        token = token.strip().lower()
        if not token or token in _QUERY_STOPWORDS:
            continue
        if len(token) == 1 and not token.isascii():
            continue
        if _ASCII_TOKEN_RE.fullmatch(token) or _CJK_SPAN_RE.fullmatch(token):
            terms.append(token)

    return list(dict.fromkeys(terms))


def looks_overview_query(query: str) -> bool:
    q = _normalize_text(query)
    if not q:
        return False

    patterns = (
        "什么是",
        "是什么",
        "介绍",
        "介绍一下",
        "讲讲",
        "说说",
        "解释",
        "说明",
        "概述",
        "定义",
        "含义",
    )
    return any(p in q for p in patterns)


def exact_match_boost(query: str, text: str) -> float:
    """
    Deterministic lexical boost for the query subject.

    BM25 is good at ranking words, but short overview queries often contain only
    one useful term. This boost makes exact acronym/term matches and definition
    sentences win over loose semantic neighbors.
    """
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return 0.0

    focus_terms = extract_focus_terms(query)
    if not focus_terms:
        return 0.0

    normalized_query = _normalize_text(query)
    overview_query = looks_overview_query(query)
    score = 0.0

    for term in focus_terms:
        if _ASCII_TOKEN_RE.fullmatch(term):
            matches = list(re.finditer(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", normalized_text))
        else:
            matches = list(re.finditer(re.escape(term), normalized_text))

        if not matches:
            continue

        score += min(len(matches), 5) * 1.5

        first_pos = matches[0].start()
        if first_pos <= 12:
            score += 1.5

        if overview_query:
            window = normalized_text[first_pos : first_pos + 80]
            if any(marker in window for marker in ("是一种", "是一个", "指的是", "retrieval-augmented")):
                score += 4.0
            if "核心思想" in normalized_query and "核心思想" in window:
                score += 2.0
            if any(word in normalized_query for word in ("优势", "优点")) and any(marker in window for marker in ("主要优势", "优势", "优点")):
                score += 2.0

            prefix = normalized_text[max(0, first_pos - 20) : first_pos]
            if any(modifier in prefix for modifier in ("agentic ", "agentic", "advanced ", "semantic ")):
                score -= 4.0

    return max(score, 0.0)


def keyword_score(text: str, query: str) -> float:
    """
    保留兼容旧逻辑的简单关键词计分函数。
    """
    query_tokens = extract_focus_terms(query) or tokenize(query)
    text_lower = _normalize_text(text)

    score = 0.0
    for token in query_tokens:
        if not token:
            continue
        if _ASCII_TOKEN_RE.fullmatch(token):
            if re.search(rf"(?<![a-z0-9_]){re.escape(token)}(?![a-z0-9_])", text_lower):
                score += 1.0
        elif token in text_lower:
            score += 1.0

    return score + exact_match_boost(query, text)


def bm25_rerank(query: str, chunks: List[Dict]) -> List[Dict]:
    """
    使用 BM25 对已有候选 chunks 进行词法打分。

    输入：
    - query: 用户问题
    - chunks: 候选 chunk 列表，每个元素至少包含:
        {
            "text": "...",
            "document_id": ...,
            "score": ...   # 向量检索阶段返回的分数/距离
        }

    输出：
    - 在每个 chunk 上新增 keyword_score 字段（BM25 分数）
    """
    if not chunks:
        return []

    corpus = [chunk.get("text", "") for chunk in chunks]
    tokenized_corpus = [tokenize(text) for text in corpus]
    query_tokens = tokenize(query)

    # 防止空语料/空 query 报错
    if not query_tokens or all(len(doc_tokens) == 0 for doc_tokens in tokenized_corpus):
        enriched_chunks = []
        for chunk in chunks:
            item = dict(chunk)
            item["keyword_score"] = 0.0
            enriched_chunks.append(item)
        return enriched_chunks

    bm25 = BM25Okapi(tokenized_corpus) if BM25Okapi is not None else _SimpleBM25(tokenized_corpus)
    bm25_scores = bm25.get_scores(query_tokens)

    enriched_chunks: List[Dict] = []
    for chunk, score in zip(chunks, bm25_scores):
        item = dict(chunk)
        exact_score = exact_match_boost(query, item.get("text", ""))
        item["bm25_score"] = float(score)
        item["exact_match_score"] = float(exact_score)
        item["keyword_score"] = float(score) + float(exact_score)
        item["query_tokens"] = query_tokens
        item["focus_terms"] = extract_focus_terms(query)
        enriched_chunks.append(item)

    return enriched_chunks
