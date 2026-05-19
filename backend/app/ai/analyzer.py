import json
import re
from urllib.parse import urlparse
from loguru import logger

from app.search.duckduckgo_search import search_web
from app.search.content_extractor import extract_content_parallel
from app.semantic.embeddings import create_embedding, create_embeddings_batch
from app.semantic.vector_store import VectorStore
from app.ai.ai_provider import generate, detect_provider


def _parse_domain(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def _build_context(docs: list[dict]) -> str:
    """Build a context string from ranked documents."""
    parts = []
    for i, doc in enumerate(docs, 1):
        content = doc.get("full_text") or doc.get("snippet") or ""
        parts.append(f"[{i}] {doc['title']}\nURL: {doc['url']}\n{content}")
    return "\n\n".join(parts)


def _normalize_sentiment(sent: dict) -> dict:
    total = sent.get("positive", 0) + sent.get("negative", 0) + sent.get("neutral", 0)
    if total > 0 and abs(total - 1.0) > 0.05:
        for k in ("positive", "negative", "neutral"):
            sent[k] = round(sent.get(k, 0) / total, 3)
    return sent


def analyze_query(query: str, api_key: str) -> dict:
    """
    Hybrid AI Search Pipeline:
    1. Search web (DuckDuckGo)
    2. Extract full content (trafilatura, async parallel)
    3. Create embeddings (sentence-transformers)
    4. Rank with FAISS vector similarity
    5. Send top documents to AI for analysis
    6. Return structured result
    """
    api_key = (api_key or "").strip()

    try:
        # ── Step 1: Web search ─────────────────────────────────────
        logger.info(f"[Pipeline] Step 1: Searching for '{query}'")
        search_results = search_web(query, max_results=10)
        if not search_results:
            return {"error": "Не вдалося отримати результати пошуку. Спробуйте ще раз."}

        # ── Step 2: Extract full content async ─────────────────────
        logger.info(f"[Pipeline] Step 2: Extracting content from {len(search_results)} URLs")
        urls = [r["url"] for r in search_results]
        extracted = extract_content_parallel(urls)

        docs = []
        for r in search_results:
            full_text = extracted.get(r["url"])
            docs.append({
                "title":     r["title"],
                "url":       r["url"],
                "domain":    r["domain"],
                "snippet":   r["snippet"],
                "full_text": full_text,
            })

        # ── Step 3: Create embeddings ──────────────────────────────
        logger.info("[Pipeline] Step 3: Creating embeddings")
        texts_for_embed = [
            (d["full_text"] or d["snippet"] or d["title"])
            for d in docs
        ]
        doc_embeddings = create_embeddings_batch(texts_for_embed)
        query_embedding = create_embedding(query)

        # ── Step 4: Semantic ranking with FAISS ───────────────────
        logger.info("[Pipeline] Step 4: Semantic ranking (FAISS)")
        store = VectorStore()
        store.add_documents(doc_embeddings, docs)
        top_docs = store.search(query_embedding, k=5)

        # ── Step 5: AI analysis ────────────────────────────────────
        logger.info(f"[Pipeline] Step 5: AI analysis ({detect_provider(api_key)})")
        context = _build_context(top_docs)
        user_message = f'Запит: "{query}"\n\nМатеріали:\n{context}'
        raw_text = generate(api_key, user_message)

        # ── Step 6: Parse & normalize result ──────────────────────
        raw_text = re.sub(r"```json|```", "", raw_text).strip()
        json_match = re.search(r'\{[\s\S]*\}', raw_text)
        if not json_match:
            return {"error": "Модель не повернула JSON", "raw": raw_text[:400]}

        data = json.loads(json_match.group(0))

        data["sentiment"] = _normalize_sentiment(data.get("sentiment", {}))

        if not data.get("sources"):
            data["sources"] = [
                {"title": d["title"], "url": d["url"], "domain": d["domain"]}
                for d in top_docs
            ]

        logger.info("[Pipeline] Completed successfully")
        return data

    except Exception as e:
        err = str(e)
        logger.error(f"Pipeline error: {err}")

        if "ConnectionError" in type(e).__name__ or "11434" in err:
            return {"error": "Ollama не запущена. Виконайте: ollama serve"}
        if "API_KEY_INVALID" in err or "API key not valid" in err:
            return {"error": "Невірний API ключ"}
        if "quota" in err.lower() or "429" in err or "rate_limit" in err.lower():
            return {"error": "Перевищено ліміт запитів. Спробуйте через хвилину."}
        return {"error": f"Помилка аналізу: {err}"}
