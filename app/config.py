# 建立配置意识
# BaseSettings 会自动从环境变量 / .env 读取配置（以后你会用到）
from pydantic_settings import BaseSettings

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
    secret_key:str = "dev-sectre-key"
    # algorithm=HS256：常见对称签名算法（签发和验证用同一个 secret）
    algorithm:str = "HS256"
    # access_token_expire_minutes：控制 token 多久过期（过期后 decode 会失败）
    access_token_expire_minutes:int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# settings 是全局配置对象，以后 anywhere import 使用
settings = Settings()
