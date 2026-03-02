# app/services/embedding_service.py
from __future__ import annotations

from typing import List
from sentence_transformers import SentenceTransformer
import os
import numpy as np


class EmbeddingService:
    """
    负责：文本 -> 向量
    注意：模型初始化很慢，所以应该只初始化一次，然后复用这个实例。
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        local_path: str = "storage/models/all-MiniLM-L6-v2",
        default_batch_size: int = 32,   # ✅ 新增：默认批大小
    ):
        self.default_batch_size = default_batch_size

        # 本地存在就走本地（离线环境稳）
        if os.path.isdir(local_path):
            self.model = SentenceTransformer(local_path)
        else:
            # 本地没有才走在线
            self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: List[str], batch_size: int | None = None) -> List[List[float]]:
        """
        批量 embedding（Day26 关键点：不要 for 循环逐条 encode）
        """
        if not texts:
            return []

        bs = batch_size or self.default_batch_size

        vectors = self.model.encode(
            texts,
            batch_size=bs,               # ✅ 新增：显式批处理
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,   # 归一化：配合 cosine 检索更稳
        )

        # ✅ 推荐：转 float32，节省内存/存储
        return vectors.astype(np.float32).tolist()

    def embed_query(self, query: str, batch_size: int | None = None) -> List[float]:
        # query 也复用同一套批量接口
        return self.embed_texts([query], batch_size=batch_size)[0]