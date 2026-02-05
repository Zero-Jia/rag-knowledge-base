from __future__ import annotations

from functools import lru_cache
from typing import List,Dict,Any,Optional

from sentence_transformers import CrossEncoder

@lru_cache(maxsize=1)
def _get_model()->CrossEncoder:
    """
    只加载一次模型，避免每个请求都重新下载/初始化（否则会非常慢）。
    """
    model = CrossEncoder("storage/models/ms-marco-MiniLM-L-6-v2")
    return model

class RerankService:
    def __init__(self):
        self.model = _get_model()

    def rerank(self,query:str,chunks:List[Dict[str,Any]])->List[Dict[str,Any]]:
        """
        chunks: [{"text": "...", ...}, ...]
        返回：按 rerank_score 降序排列后的 chunks，并在每个 chunk 中写入 rerank_score
        """
        if not chunks:
            return []
        
        # 1) 组 pair: (query, doc_text)
        pairs = [(query,c.get("text","")) for c in chunks]
        # 2) cross-encoder 打分（越大越相关）
        scores = self.model.predict(pairs)
        # 3) 写回分数 + 排序
        for chunk,score in zip(chunks,scores):
            chunk["rerank_score"] = float(score)

        chunks.sort(key=lambda x:x.get("rerank_score",float("-inf")),reverse=True)
        return chunks     
