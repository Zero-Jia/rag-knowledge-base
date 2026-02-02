# 实现 EmbeddingService（只初始化一次模型）
from __future__ import annotations

from typing import List
from sentence_transformers import SentenceTransformer
import os

class EmbeddingService:
    """
    负责：文本 -> 向量
    注意：模型初始化很慢，所以应该只初始化一次，然后复用这个实例。
    """
     
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        local_path: str = "storage/models/all-MiniLM-L6-v2",
    ):
        # 本地存在就走本地（离线环境稳）
        if os.path.isdir(local_path):
            self.model = SentenceTransformer(local_path)
        else:
            # 本地没有才走在线
            self.model = SentenceTransformer(model_name)

    def embed_texts(self,texts:List[str])->List[List[float]]:
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            show_progress_bar= False,
            convert_to_numpy= True,
            normalize_embeddings= True,  # 是否归一化可以后面再讨论
        )
        return vectors.tolist()
    
    def embed_query(self,query:str)->List[float]:
        return self.embed_texts([query])[0]