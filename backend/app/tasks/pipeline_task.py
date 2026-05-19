"""
app/tasks/pipeline_task.py

Celery task wrapping the full analysis pipeline.
The HTTP handler starts the task and returns a task_id immediately;
the client polls /api/v1/task/<id> or uses SSE /api/v1/stream/<id>.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import redis
from celery import Celery
from celery.utils.log import get_task_logger


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery("webanalyzer", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=3600,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

logger = get_task_logger(__name__)

# Separate Redis client for SSE progress updates
_redis = redis.from_url(REDIS_URL, decode_responses=True)


def _push_progress(task_id: str, step: int, total: int, message: str) -> None:
    """
    Publish progress to Redis so SSE endpoint can stream it.
    Also store latest progress for polling clients.
    """
    payload = json.dumps(
        {"step": step, "total": total, "message": message},
        ensure_ascii=False,
    )
    _redis.publish(f"progress:{task_id}", payload)
    _redis.setex(f"progress_state:{task_id}", 120, payload)


def _normalize_sentiment(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize sentiment values if model returned percentages instead of 0..1 floats.
    """
    sent = data.get("sentiment") or {}

    positive = float(sent.get("positive", 0) or 0)
    negative = float(sent.get("negative", 0) or 0)
    neutral = float(sent.get("neutral", 0) or 0)

    total = positive + negative + neutral

    if total > 0 and abs(total - 1.0) > 0.05:
        positive = round(positive / total, 3)
        negative = round(negative / total, 3)
        neutral = round(neutral / total, 3)

    sent["positive"] = positive
    sent["negative"] = negative
    sent["neutral"] = neutral

    if not sent.get("overall"):
        if positive >= negative and positive >= neutral:
            sent["overall"] = "positive"
        elif negative >= positive and negative >= neutral:
            sent["overall"] = "negative"
        else:
            sent["overall"] = "neutral"

    data["sentiment"] = sent
    data["overall"] = data.get("overall") or sent.get("overall", "neutral")

    return data


def _extract_json_from_model(raw_text: str) -> dict[str, Any]:
    """
    Extract JSON object from model response.
    """
    cleaned = re.sub(r"```json|```", "", raw_text).strip()
    json_match = re.search(r"\{[\s\S]*\}", cleaned)

    if not json_match:
        raise ValueError(f"Модель не повернула JSON. Raw: {cleaned[:400]}")

    return json.loads(json_match.group(0))


def _build_context(docs_list: list[dict[str, Any]]) -> str:
    """
    Build text context for the AI model from ranked documents.
    """
    parts = []

    for i, doc in enumerate(docs_list, 1):
        content = doc.get("full_text") or doc.get("snippet") or ""
        score = doc.get("_relevance", 0)

        parts.append(
            f"[{i}] {doc.get('title', 'Без назви')} "
            f"(relevance={score:.2f})\n"
            f"URL: {doc.get('url', '')}\n"
            f"{content}"
        )

    return "\n\n".join(parts)


@celery_app.task(bind=True, name="pipeline.analyze")
def run_pipeline(
    self,
    query: str,
    api_key: str,
    user_id: int | None = None,
    depth: str = "standard",
    max_results: int = 10,
    lang: str = "auto",
) -> dict[str, Any]:
    """
    Execute the full Hybrid AI Search Pipeline as a background Celery task.

    Arguments must match app/routes.py:
        run_pipeline.delay(query, api_key, g.user_id, depth, max_results, lang)
    """
    task_id = self.request.id
    logger.info(
        "[Task %s] Starting pipeline query=%r user_id=%s depth=%s max_results=%s lang=%s",
        task_id,
        query,
        user_id,
        depth,
        max_results,
        lang,
    )

    try:
        # Import here to avoid circular imports at module load
        from app.ai.ai_provider import detect_provider, generate
        from app.cache.redis_cache import get_cached, save_cache
        from app.database.db import save_search
        from app.scoring.text_scorer import deduplicate_docs, score_relevance
        from app.search.content_extractor import extract_content_parallel
        from app.search.duckduckgo_search import search_web
        from app.semantic.chroma_store import ChromaStore
        from app.semantic.embeddings import create_embedding, create_embeddings_batch

        total_steps = 6

        # Cache check.
        # Important: even if result is cached, save it to current user's history.
        cached = get_cached(query, depth=depth, lang=lang)

        if cached:
            logger.info("[Task %s] Cache hit", task_id)
            _push_progress(task_id, 6, total_steps, "Результат взято з кешу")

            cached_result = dict(cached)
            search_id = save_search(
                query=query,
                result=cached_result,
                user_id=user_id,
                depth=depth,
                lang=lang,
            )

            cached_result["id"] = search_id
            cached_result["cached"] = True

            return cached_result

        # Step 1: Web Search
        _push_progress(task_id, 1, total_steps, "Пошук в інтернеті…")

        try:
            max_results = int(max_results)
        except Exception:
            max_results = 10

        if depth not in {"fast", "standard", "deep"}:
            depth = "standard"

        search_results = search_web(query, max_results=max_results)

        if not search_results:
            return {
                "error": "Не вдалося отримати результати пошуку. Спробуйте ще раз."
            }

        # Step 2: Extract content
        if depth == "fast":
            _push_progress(
                task_id,
                2,
                total_steps,
                "Швидкий режим: використання сніпетів без повного завантаження сторінок…",
            )

            docs = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "domain": r.get("domain", ""),
                    "snippet": r.get("snippet", ""),
                    "full_text": None,
                }
                for r in search_results
            ]
        else:
            _push_progress(
                task_id,
                2,
                total_steps,
                f"Завантаження {len(search_results)} сторінок…",
            )

            urls = [r["url"] for r in search_results if r.get("url")]
            extracted = extract_content_parallel(urls)

            docs = []

            for r in search_results:
                full_text = extracted.get(r.get("url"))

                docs.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "domain": r.get("domain", ""),
                        "snippet": r.get("snippet", ""),
                        "full_text": full_text,
                    }
                )

        # Deduplication
        docs = deduplicate_docs(docs, threshold=0.72)

        if not docs:
            return {
                "error": "Не вдалося підготувати документи для аналізу."
            }

        # Step 3: Embeddings
        _push_progress(task_id, 3, total_steps, "Створення семантичних векторів…")

        texts_for_embed = [
            d.get("full_text") or d.get("snippet") or d.get("title") or ""
            for d in docs
        ]

        doc_embeddings = create_embeddings_batch(texts_for_embed)
        query_embedding = create_embedding(query)

        # Step 4: ChromaDB semantic ranking
        _push_progress(task_id, 4, total_steps, "Семантичне ранжування ChromaDB…")

        store = ChromaStore()
        store.add_documents(doc_embeddings, docs, query)

        top_k = 3 if depth == "fast" else 5 if depth == "standard" else 8
        top_docs = store.search(query_embedding, k=top_k)

        # Relevance rescoring
        for doc in top_docs:
            text = doc.get("full_text") or doc.get("snippet") or ""
            doc["_relevance"] = score_relevance(text, query)

        top_docs.sort(key=lambda d: d.get("_relevance", 0), reverse=True)

        # Step 5: AI analysis
        provider = detect_provider(api_key)

        _push_progress(task_id, 5, total_steps, f"AI аналіз ({provider})…")

        context = _build_context(top_docs)

        lang_labels = {
            "auto": "мовою запиту користувача",
            "ru": "російською мовою",
            "uk": "українською мовою",
            "en": "англійською мовою",
        }

        lang_hint = lang_labels.get(lang, lang_labels["auto"])

        user_message = (
            f'Запит: "{query}"\n\n'
            f"Мова відповіді: {lang_hint}.\n\n"
            f"Матеріали:\n{context}"
        )

        raw_text = generate(api_key, user_message, lang=lang)

        # Step 6: Parse result
        _push_progress(task_id, 6, total_steps, "Обробка результатів…")

        data = _extract_json_from_model(raw_text)
        data = _normalize_sentiment(data)

        if not data.get("sources"):
            data["sources"] = [
                {
                    "title": d.get("title", ""),
                    "url": d.get("url", ""),
                    "domain": d.get("domain", ""),
                }
                for d in top_docs
            ]

        data["sources_used"] = len(top_docs)

        # Save to cache and DB
        save_cache(query, data, depth=depth, lang=lang)

        search_id = save_search(
            query=query,
            result=data,
            user_id=user_id,
            depth=depth,
            lang=lang,
        )

        data["id"] = search_id

        logger.info("[Task %s] Pipeline completed db_id=%s", task_id, search_id)

        return data

    except Exception as e:
        err = str(e)

        logger.error("[Task %s] Error: %s", task_id, err)

        if "ConnectionError" in type(e).__name__ or "11434" in err:
            return {"error": "Ollama не запущена. Виконайте: ollama serve"}

        if "API_KEY_INVALID" in err or "API key not valid" in err:
            return {"error": "Невірний API ключ"}

        if "quota" in err.lower() or "429" in err or "rate_limit" in err.lower():
            return {"error": "Перевищено ліміт запитів. Спробуйте через хвилину."}

        return {"error": f"Помилка аналізу: {err}"}