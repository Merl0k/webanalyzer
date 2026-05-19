import hashlib
import json

import redis
from loguru import logger


CACHE_TTL = 3600  # 1 hour

_client = None


def _get_client():
    global _client

    if _client is None:
        try:
            _client = redis.Redis(
                host="redis",
                port=6379,
                decode_responses=True,
            )
            _client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            _client = None

    return _client


def _cache_key(query: str, depth: str = "standard", lang: str = "auto") -> str:
    raw = f"{query.strip().lower()}|{depth}|{lang}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    return f"search:{digest}"


def get_cached(
    query: str,
    depth: str = "standard",
    lang: str = "auto",
) -> dict | None:
    client = _get_client()

    if client is None:
        return None

    try:
        data = client.get(_cache_key(query, depth, lang))

        if data:
            return json.loads(data)

    except Exception as e:
        logger.warning(f"Cache read error: {e}")

    return None


def save_cache(
    query: str,
    result: dict,
    depth: str = "standard",
    lang: str = "auto",
):
    client = _get_client()

    if client is None:
        return

    try:
        client.set(
            _cache_key(query, depth, lang),
            json.dumps(result, ensure_ascii=False),
            ex=CACHE_TTL,
        )
        logger.debug(
            f"Cached result for query='{query}' depth='{depth}' lang='{lang}' "
            f"(TTL={CACHE_TTL}s)"
        )

    except Exception as e:
        logger.warning(f"Cache write error: {e}")