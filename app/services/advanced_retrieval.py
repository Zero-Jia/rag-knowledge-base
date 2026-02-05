# 把 Rerank 接进检索链路（Recall → Rerank）
from __future__ import annotations
from typing import List,Dict,Any
from app.services.hybrid_retrieval import hybrid_retrieve
from app.services.rerank_service import RerankService

def retrieve_with_rerank(query:str,top_k:int = 5,recall_multiplier:int=2)-> List[Dict[str,Any]]:
    """
    标准两阶段：
      1) recall：hybrid 先召回 top_k * recall_multiplier 个候选
      2) rerank：cross-encoder 精排
      3) return：取最终 top_k
    """
    recall_k = max(top_k*recall_multiplier,top_k)
    # 1) 召回更多候选
    candidates = hybrid_retrieve(query,recall_k)
    # 2) 精排（只在候选上跑）
    reranker = RerankService()
    reranked = reranker.rerank(query,candidates)
    # 3) 返回最终 top_k
    return reranked[:top_k]