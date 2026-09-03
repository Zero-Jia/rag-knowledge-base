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

    # =========================
    # Langfuse Settings (P0-5)
    # =========================
    # 总开关：False 时所有 langfuse 上报走 no-op，零 SDK 初始化、零网络调用
    LANGFUSE_ENABLED: bool = False
    # Langfuse Cloud Hobby 默认 host；自建时改为 http://localhost:3000
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    # 从 Langfuse Project Settings → API Keys 获取
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""

    # =========================
    # ReAct Agent Settings (P1-2)
    # =========================
    # 总开关：False 时三层漏斗路由全部走原 quick path，react_agent 节点零调用
    # （与 LANGFUSE_ENABLED 同款灰度/回滚策略）
    REACT_AGENT_ENABLED: bool = False
    # create_react_agent 子图 recursion_limit（LangGraph super-step 计数，
    # 每轮工具调用约 2 步；25 ≈ 最多 10 轮左右工具调用，防止 agent 无限检索）
    REACT_RECURSION_LIMIT: int = 25
    # ReAct 工具返回 JSON 中片段正文截断长度（quick path 纯函数不受影响）
    REACT_TOOL_TEXT_LIMIT: int = 800


settings = Settings()
