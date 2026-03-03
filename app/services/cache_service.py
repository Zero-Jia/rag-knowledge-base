import json
import redis
import hashlib
from typing import Any,Optional
from app.core.config import settings

REDIS_URL = settings.REDIS_URL
DEFAULT_TTL = settings.REDIS_TTL_SECONDS

redis_client = redis.Redis.from_url(REDIS_URL,decode_responses=True)

def _hash(s:str)->str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def make_cache_key(prefix: str, raw: str) -> str:
    return f"{prefix}:{_hash(raw)}"

def get_cache(key: str) -> Optional[Any]:
    val = redis_client.get(key)
    if not val:
        return None
    try:
        return json.loads(val)
    except Exception:
        return None

def set_cache(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
