# 建立配置意识
# BaseSettings 会自动从环境变量 / .env 读取配置（以后你会用到）
from pydantic_settings import BaseSettings
from typing import Literal

class RAGSettings(BaseSettings):
    """
    RAG 相关配置：检索策略、chunk参数、top_k 等
    会自动从环境变量 / .env 读取（前缀 RAG_）
    """
    chunk_size:int = 500
    chunk_overlap:int = 100
    # 可选: vector / hybrid / rerank
    retrieval_mode:Literal["vector","hybrid","rerank"] = "hybrid"
    top_k:int = 5
    rerank_candidates:int = 10

    class Config:
        env_prefix = "RAG_"          # .env: RAG_TOP_K=8
        env_file = ".env"
        env_file_encoding = "utf-8"

class Settings(BaseSettings):
    # -------------------------
    # 应用基础配置
    # -------------------------
    app_name: str = "RAG Knowledge Base Backend"
    debug: bool = True

    # -------------------------
    # JWT 相关配置（Day 4 新增）
    # -------------------------
    # secret_key：JWT 的“签名密钥”，泄露了就等于别人能伪造 token（非常重要）
    secret_key:str = "dev-secret-key"
    # algorithm=HS256：常见对称签名算法（签发和验证用同一个 secret）
    algorithm:str = "HS256"
    # access_token_expire_minutes：控制 token 多久过期（过期后 decode 会失败）
    access_token_expire_minutes:int = 60

    rag:RAGSettings = RAGSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# settings 是全局配置对象，以后 anywhere import 使用
settings = Settings()
