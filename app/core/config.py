from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = "dev"

    APP_NAME: str = "RAG Knowledge Base Backend"
    DEBUG: bool = True

    SECRET_KEY: str = "dev-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    CHUNK_MIN_LENGTH: int = 20
    HIERARCHICAL_CHUNKING_ENABLED: bool = True
    HIERARCHICAL_L1_CHUNK_SIZE: int = 2000
    HIERARCHICAL_L1_CHUNK_OVERLAP: int = 200
    HIERARCHICAL_L2_CHUNK_SIZE: int = 1000
    HIERARCHICAL_L2_CHUNK_OVERLAP: int = 120
    HIERARCHICAL_L3_CHUNK_SIZE: int = 500
    HIERARCHICAL_L3_CHUNK_OVERLAP: int = 100
    AUTO_MERGE_ENABLED: bool = True
    AUTO_MERGE_MIN_CHILDREN: int = 2
    AUTO_MERGE_PARENT_RATIO: float = 0.5
    AUTO_MERGE_MAX_PARENT_CHARS: int = 4000
    QUERY_EXPANSION_ENABLED: bool = True
    QUERY_EXPANSION_MAX_QUERIES: int = 3
    STEP_BACK_ENABLED: bool = True
    HYDE_ENABLED: bool = True
    HYDE_MAX_CHARS: int = 600
    TOP_K: int = 5
    TOP_K_MIN: int = 1
    TOP_K_MAX: int = 20
    RERANK_CANDIDATES: int = 10
    RETRIEVAL_MODE: str = "hybrid"
    RECALL_MULTIPLIER: int = 2
    MAX_CHUNKS: int = 500
    EMBED_BATCH_SIZE: int = 32

    OPENAI_API_KEY: str = "sk-ec4fd8a6112045d79e1099f6061e0905"
    OPENAI_BASE_URL: str = "https://api.deepseek.com"
    OPENAI_MODEL: str = "deepseek-chat"
    TIMEOUT_SECONDS: int = 20
    MAX_RETRIES: int = 3
    BASE_DELAY: float = 1.0

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TTL_SECONDS: int = 3600

    CHAT_STREAM_CHUNK_SIZE: int = 20
    TEXT_PREVIEW_CHARS: int = 1000
    DOCUMENT_LIST_LIMIT: int = 50
    RATE_LIMIT_COUNT: int = 5
    RATE_LIMIT_WINDOW_SECONDS: int = 10
    CHUNK_SIZE_MIN: int = 100
    CHUNK_SIZE_MAX: int = 5000
    OVERLAP_MIN: int = 0
    OVERLAP_MAX: int = 1000

    # =========================
    # Semantic Cache Settings
    # =========================
    SEMANTIC_CACHE_ENABLED: bool = True
    SEMANTIC_CACHE_COLLECTION_NAME: str = "semantic_cache"
    SEMANTIC_CACHE_TOP_K: int = 3
    SEMANTIC_CACHE_THRESHOLD: float = 0.93
    SEMANTIC_CACHE_MAX_QUESTION_LENGTH: int = 100
    SEMANTIC_CACHE_MIN_QUESTION_LENGTH: int = 2
    SEMANTIC_CACHE_PERSIST_DIR: str = "storage/chroma"

    # 是否要求 user_id 一致才允许命中语义缓存
    SEMANTIC_CACHE_REQUIRE_SAME_USER: bool = True

    # 是否要求 retrieval_mode 一致才允许命中语义缓存
    SEMANTIC_CACHE_REQUIRE_SAME_MODE: bool = True


settings = Settings()
