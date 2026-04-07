import json
import redis
import hashlib
import logging
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger("rag.cache")

REDIS_URL = settings.REDIS_URL
DEFAULT_TTL = settings.REDIS_TTL_SECONDS

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def make_cache_key(prefix: str, raw: str) -> str:
    return f"{prefix}:{_hash(raw)}"


def get_cache(key: str) -> Optional[Any]:
    try:
        val = redis_client.get(key)
        if not val:
            return None
        return json.loads(val)
    except Exception as e:
        logger.warning(f"redis get_cache failed | key={key} | err={e}")
        return None


def set_cache(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    try:
        redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"redis set_cache failed | key={key} | err={e}")


def delete_cache(key: str) -> None:
    try:
        redis_client.delete(key)
    except Exception as e:
        logger.warning(f"redis delete_cache failed | key={key} | err={e}")