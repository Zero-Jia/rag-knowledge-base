# 实现 Hybrid 融合检索
from app.services.retrieval_service import retrieve_chunks
from app.services.keyword_search import keyword_score

def hybrid_retrieve(query:str,top_k:int = 5):
    """
    Hybrid Search（简化工程版）：
    1) 先做向量检索拿候选集（top_k * 2）
    2) 对候选集做关键词打分
    3) 融合得分后排序
    """
    # 1) 候选集拉大：防止纯向量 top_k 把“精确匹配”的结果漏掉
    candidate_k = max(top_k*2,top_k)
    vector_results = retrieve_chunks(query,candidate_k)
    # 约定：retrieve_chunks 返回形如：
    # [{"text": "...", "score": <distance or similarity>, ...}, ...]
    for r in vector_results:
        kw = keyword_score(r.get("text", ""), query)
        r["keyword_score"] = kw
        # 注意：你 Day13 里 retrieve_chunks 的 score 是什么？
        # 常见两种：
        # A) distance（越小越好） -> 用 1/(distance+eps)
        # B) similarity（越大越好）-> 直接用 similarity
        #
        # 下面用 A) distance 写（与你规划一致）：
        dist = float(r.get("score", 0.0))
        dense_part = 1.0 / (dist + 1e-6)
        # 2) 加权融合：0.7 语义 + 0.3 精确
        r["final_score"] = dense_part * 0.7 + kw * 0.3

    vector_results.sort(key=lambda x:x.get("final_score",0.0),reverse=True)
    return vector_results[:top_k]