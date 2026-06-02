"""app/routes.py — REST API v3 (prefix /api/v1)"""
import json, re, time
from flask import Blueprint, request, jsonify, Response, stream_with_context, g, make_response
from loguru import logger
from app import limiter
from app.database import db as database
from app.cache.redis_cache import get_cached, save_cache, _get_client as get_redis
from app.auth.decorators import require_auth
from app.auth.jwt_utils import make_access_token, make_refresh_token, decode_token
from app.auth.crypto import encrypt, decrypt
import bcrypt
import jwt as pyjwt

bp = Blueprint("api", __name__, url_prefix="/api/v1")

@bp.route("/", methods=["GET"], strict_slashes=False)
def api_index():
    return jsonify(
        {
            "name": "WebAnalyzer v3 API",
            "version": "3.0.0",
            "status": "ok",
            "docs": "/api/v1/docs",
            "openapi": "/api/v1/openapi.json",
            "health": "/api/v1/health",
            "endpoints": {
                "auth": "/api/v1/auth",
                "analyze": "/api/v1/analyze",
                "history": "/api/v1/history",
                "stats": "/api/v1/stats",
                "tags": "/api/v1/tags",
                "compare": "/api/v1/compare",
            },
        }
    )

# ── AUTH ──────────────────────────────────────────────────────────────────────

@bp.route("/auth/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    data  = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    pwd   = (data.get("password") or "").strip()
    if not email or "@" not in email:
        return jsonify({"error": "Невалідний email"}), 400
    if len(pwd) < 8:
        return jsonify({"error": "Пароль мінімум 8 символів"}), 400
    if database.get_user_by_email(email):
        return jsonify({"error": "Email вже зареєстровано"}), 409
    pw_hash = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
    user = database.create_user(email, pw_hash)
    return jsonify({"ok": True, "user": {"id": user["id"], "email": user["email"]}}), 201

@bp.route("/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data  = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    pwd   = (data.get("password") or "").strip()
    user  = database.get_user_by_email(email)
    if not user or not bcrypt.checkpw(pwd.encode(), user["password_hash"].encode()):
        return jsonify({"error": "Невірний email або пароль"}), 401
    access  = make_access_token(user["id"])
    refresh = make_refresh_token(user["id"])
    resp = make_response(jsonify({"ok": True, "user": {"id": user["id"], "email": user["email"], "theme": user["theme"]}}))
    _set_cookie(resp, "access_token",  access,  max_age=3600)
    _set_cookie(resp, "refresh_token", refresh, max_age=86400*30)
    return resp

@bp.route("/auth/refresh", methods=["POST"])
def refresh_tokens():
    token = request.cookies.get("refresh_token")
    if not token: return jsonify({"error": "Refresh token відсутній"}), 401
    try: payload = decode_token(token)
    except pyjwt.PyJWTError: return jsonify({"error": "Невалідний refresh token"}), 401
    if payload.get("type") != "refresh": return jsonify({"error": "Невірний тип токена"}), 401
    uid = payload["sub"]
    resp = make_response(jsonify({"ok": True}))
    _set_cookie(resp, "access_token",  make_access_token(uid),  max_age=3600)
    _set_cookie(resp, "refresh_token", make_refresh_token(uid), max_age=86400*30)
    return resp

@bp.route("/auth/logout", methods=["POST"])
def logout():
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("access_token"); resp.delete_cookie("refresh_token")
    return resp

@bp.route("/auth/me", methods=["GET"])
@require_auth
def me():
    return jsonify(g.user)

# ── PROFILE / API KEYS ────────────────────────────────────────────────────────

@bp.route("/profile/keys", methods=["GET"])
@require_auth
def list_keys():
    return jsonify(database.get_api_keys(g.user_id))

@bp.route("/profile/keys", methods=["POST"])
@require_auth
def save_key():
    data     = request.get_json() or {}
    provider = (data.get("provider") or "").strip()
    raw_key  = (data.get("key") or "").strip()
    model    = (data.get("model") or "").strip()
    if provider not in ("gemini", "groq", "ollama"):
        return jsonify({"error": "Невірний провайдер"}), 400
    if not raw_key: return jsonify({"error": "Ключ порожній"}), 400
    return jsonify(database.save_api_key(g.user_id, provider, encrypt(raw_key), model))

@bp.route("/profile/keys/<provider>", methods=["DELETE"])
@require_auth
def delete_key(provider):
    database.delete_api_key(g.user_id, provider)
    return jsonify({"ok": True})

@bp.route("/profile/theme", methods=["POST"])
@require_auth
def set_theme():
    theme = (request.get_json() or {}).get("theme", "dark")
    database.update_user_theme(g.user_id, theme)
    return jsonify({"ok": True})

# ── ANALYZE ───────────────────────────────────────────────────────────────────

@bp.route("/analyze", methods=["POST"])
@require_auth
@limiter.limit("10 per hour", key_func=lambda: str(g.user_id) if hasattr(g, "user_id") else request.remote_addr)
def analyze():
    data  = request.get_json() or {}
    query = (data.get("query") or "").strip()
    depth = data.get("depth", "standard")
    lang = (data.get("lang") or "auto").strip().lower()

    if lang not in ("auto", "ru", "uk", "en"):
        lang = "auto"
    if not query: return jsonify({"error": "Запит не може бути порожнім"}), 400
    depth_config = {"fast": 5, "standard": 10, "deep": 20}
    max_results  = depth_config.get(depth, 10)
    api_key = _get_user_api_key(g.user_id)
    if not api_key:
        return jsonify({"error": "Спочатку додайте API ключ у налаштуваннях профілю"}), 400
    logger.info(f"[User {g.user_id}] Search: '{query}' depth={depth}")
    cached = get_cached(query, depth=depth, lang=lang)
    if cached:
        return jsonify({**cached, "cached": True})
    try:
        from app.tasks.pipeline_task import run_pipeline
        task = run_pipeline.delay(query, api_key, g.user_id, depth, max_results, lang)
        return jsonify({"task_id": task.id, "status": "queued"})
    except Exception as e:
        logger.warning(f"Celery unavailable ({e}), running synchronously")
        result = _pipeline_direct(query, api_key, g.user_id, depth, max_results, lang)
        if "error" in result: return jsonify(result), 400
        return jsonify(result)

# ── TASK / SSE ────────────────────────────────────────────────────────────────

@bp.route("/task/<task_id>", methods=["GET"])
def task_status(task_id):
    try:
        from app.tasks.pipeline_task import celery_app
        result = celery_app.AsyncResult(task_id)
        if result.state == "PENDING": return jsonify({"status": "pending"})
        if result.state == "STARTED": return jsonify({"status": "running"})
        if result.state == "SUCCESS": return jsonify({"status": "done", "result": result.result})
        if result.state == "FAILURE": return jsonify({"status": "error", "error": str(result.result)}), 500
        return jsonify({"status": result.state.lower()})
    except Exception as e: return jsonify({"status": "error", "error": str(e)}), 500

@bp.route("/stream/<task_id>", methods=["GET"])
def stream_progress(task_id):
    def gen():
        redis_client = get_redis()
        if not redis_client: yield 'data: {"error":"Redis unavailable"}\n\n'; return
        pubsub = redis_client.pubsub(); pubsub.subscribe(f"progress:{task_id}")
        try:
            from app.tasks.pipeline_task import celery_app
        except Exception: yield 'data: {"error":"Celery unavailable"}\n\n'; return
        deadline = time.time() + 180
        while time.time() < deadline:
            msg = pubsub.get_message(timeout=0.5)
            if msg and msg["type"] == "message":
                yield f"data: {msg['data']}\n\n"
                try:
                    p = json.loads(msg["data"])
                    if p.get("step") == p.get("total"): break
                except Exception: pass
            result = celery_app.AsyncResult(task_id)
            if result.state == "SUCCESS":
                yield f"data: {json.dumps({'step':6,'total':6,'message':'Готово!'})}\n\n"
                yield f"data: {json.dumps({'done':True,'result':result.result})}\n\n"; break
            if result.state == "FAILURE":
                yield f"data: {json.dumps({'error':str(result.result)})}\n\n"; break
            yield ": heartbeat\n\n"
        pubsub.unsubscribe(); pubsub.close()
    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})

# ── HISTORY ───────────────────────────────────────────────────────────────────

@bp.route("/history", methods=["GET"])
@require_auth
def history():
    return jsonify(database.get_history(
        int(request.args.get("limit", 20)), int(request.args.get("offset", 0)),
        g.user_id, request.args.get("tag_id", type=int)))

@bp.route("/history/<int:search_id>", methods=["GET"])
@require_auth
def get_one(search_id):
    row = database.get_search_by_id(search_id, g.user_id)

    if not row:
        return jsonify({"error": "Не знайдено або немає доступу"}), 404

    return jsonify(row)

@bp.route("/history/<int:search_id>", methods=["DELETE"])
@require_auth
def delete_one(search_id):
    deleted = database.delete_search(search_id, g.user_id)

    if not deleted:
        return jsonify({"error": "Не знайдено або немає доступу"}), 404

    return jsonify({"ok": True})

# ── SHARE ─────────────────────────────────────────────────────────────────────

@bp.route("/history/<int:search_id>/share", methods=["POST"])
@require_auth
def create_share(search_id):
    token = database.create_share_link(search_id, g.user_id)

    if not token:
        return jsonify({"error": "Не знайдено або немає доступу"}), 404

    return jsonify({"token": token, "url": f"/share/{token}"})

@bp.route("/share/<token>", methods=["GET"])
def view_shared(token):
    row = database.get_search_by_share_token(token)
    if not row: return jsonify({"error": "Посилання недійсне або закінчилось"}), 404
    return jsonify(row)

# ── TAGS ──────────────────────────────────────────────────────────────────────

@bp.route("/tags", methods=["GET"])
@require_auth
def list_tags():
    return jsonify(database.get_tags(g.user_id))

@bp.route("/tags", methods=["POST"])
@require_auth
def create_tag():
    data = request.get_json() or {}; name = (data.get("name") or "").strip()
    if not name: return jsonify({"error": "Назва тегу порожня"}), 400
    return jsonify(database.create_tag(g.user_id, name, data.get("color", "#4fffb0")))

@bp.route("/tags/<int:tag_id>", methods=["DELETE"])
@require_auth
def delete_tag(tag_id):
    database.delete_tag(g.user_id, tag_id); return jsonify({"ok": True})

@bp.route("/history/<int:search_id>/tags/<int:tag_id>", methods=["POST"])
@require_auth
def add_tag(search_id, tag_id):
    ok = database.add_tag_to_search(search_id, tag_id, g.user_id)

    if not ok:
        return jsonify({"error": "Результат або тег не знайдено"}), 404

    return jsonify({"ok": True})

@bp.route("/history/<int:search_id>/tags/<int:tag_id>", methods=["DELETE"])
@require_auth
def remove_tag(search_id, tag_id):
    ok = database.remove_tag_from_search(search_id, tag_id, g.user_id)

    if not ok:
        return jsonify({"error": "Результат або тег не знайдено"}), 404

    return jsonify({"ok": True})

# ── COLLECTIONS ───────────────────────────────────────────────────────────────

@bp.route("/collections", methods=["GET"])
@require_auth
def list_collections():
    return jsonify(database.get_collections(g.user_id))

@bp.route("/collections", methods=["POST"])
@require_auth
def create_collection():
    data = request.get_json() or {}; name = (data.get("name") or "").strip()
    if not name: return jsonify({"error": "Назва колекції порожня"}), 400
    return jsonify(database.create_collection(g.user_id, name, data.get("description", "")))

@bp.route("/collections/<int:col_id>/add/<int:search_id>", methods=["POST"])
@require_auth
def add_to_collection(col_id, search_id):
    ok = database.add_to_collection(search_id, col_id, g.user_id)

    if not ok:
        return jsonify({"error": "Результат або колекцію не знайдено"}), 404

    return jsonify({"ok": True})

# ── EXPORT ────────────────────────────────────────────────────────────────────

@bp.route("/history/<int:search_id>/export/<fmt>", methods=["GET"])
@require_auth
def export_result(search_id, fmt):
    row = database.get_search_by_id(search_id, g.user_id)

    if not row:
        return jsonify({"error": "Не знайдено або немає доступу"}), 404

    if fmt == "json":
        return Response(
            json.dumps(row, ensure_ascii=False, indent=2),
            mimetype="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=analysis_{search_id}.json"
            },
        )

    if fmt == "markdown":
        return Response(
            _to_markdown(row),
            mimetype="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=analysis_{search_id}.md"
            },
        )

    if fmt == "pdf":
        try:
            from app.export.pdf_export import generate_pdf

            return Response(
                generate_pdf(row),
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=analysis_{search_id}.pdf"
                },
            )
        except Exception as e:
            return jsonify({"error": f"PDF помилка: {e}"}), 500

    return jsonify({"error": "Невідомий формат"}), 400

# ── COMPARE ───────────────────────────────────────────────────────────────────

@bp.route("/compare", methods=["POST"])
@require_auth
def compare():
    ids = (request.get_json() or {}).get("ids", [])

    if not isinstance(ids, list):
        return jsonify({"error": "ids має бути списком"}), 400

    if not 2 <= len(ids) <= 3:
        return jsonify({"error": "Оберіть 2–3 результати"}), 400

    try:
        ids = [int(i) for i in ids]
    except Exception:
        return jsonify({"error": "ids мають бути числами"}), 400

    rows = [database.get_search_by_id(i, g.user_id) for i in ids]

    if any(r is None for r in rows):
        return jsonify({"error": "Один або кілька результатів не знайдені"}), 404

    return jsonify(
        {
            "queries": [r["query"] for r in rows],
            "overalls": [r["overall"] for r in rows],
            "sentiments": [r["sentiment"] for r in rows],
            "sources_cnt": [r["sources_cnt"] for r in rows],
            "key_facts": [r["key_facts"] for r in rows],
        }
    )

# ── STATS / HEALTH ────────────────────────────────────────────────────────────

@bp.route("/stats", methods=["GET"])
@require_auth
def stats():
    return jsonify(database.get_stats(g.user_id))


@bp.route("/health", methods=["GET"])
@limiter.exempt
def health():
    from app.database.db import engine
    from sqlalchemy import text as sql_text
    db_ok = redis_ok = celery_ok = False
    try:
        with engine.connect() as conn: conn.execute(sql_text("SELECT 1")); db_ok = True
    except Exception: pass
    redis_client = get_redis()
    try:
        if redis_client: redis_client.ping(); redis_ok = True
    except Exception: pass
    try:
        from app.tasks.pipeline_task import celery_app
        i = celery_app.control.inspect(timeout=1.0); celery_ok = bool(i.active())
    except Exception: pass
    return jsonify({"status":"ok" if db_ok else "degraded","db":"ok" if db_ok else "error",
                    "redis":"ok" if redis_ok else "error","celery":"ok" if celery_ok else "unavailable","version":"3.0.0"})

# ── HELPERS ───────────────────────────────────────────────────────────────────

def _get_user_api_key(user_id):
    from app.database.db import get_api_key_enc
    for provider in ("gemini", "groq", "ollama"):
        enc = get_api_key_enc(user_id, provider)
        if enc:
            try: return decrypt(enc)
            except Exception: continue
    return None

def _set_cookie(resp, name, value, max_age):
    resp.set_cookie(name, value, max_age=max_age, httponly=True, secure=False, samesite="Lax", path="/")

def _to_markdown(row):
    s = row.get("sentiment", {})
    lines = [f"# {row['query']}",
             f"*{row['created_at']} · {row['depth']} · {row['sources_cnt']} джерел*\n",
             "## Резюме", row.get("summary",""), "",
             f"## Тональність: {row['overall']}",
             "| Позитивна | Негативна | Нейтральна |","|-----------|-----------|------------|",
             f"| {s.get('positive',0):.0%} | {s.get('negative',0):.0%} | {s.get('neutral',0):.0%} |",
             "", "## Ключові факти"]
    for i, f in enumerate(row.get("key_facts",[]), 1): lines.append(f"{i}. {f}")
    lines += ["", "## Джерела"]
    for src in row.get("sources",[]): lines.append(f"- [{src.get('title','?')}]({src.get('url','#')})")
    return "\n".join(lines)

def _pipeline_direct(query, api_key, user_id, depth, max_results, lang):
    from app.search.duckduckgo_search import search_web
    from app.search.content_extractor import extract_content_parallel
    from app.semantic.embeddings import create_embedding, create_embeddings_batch
    from app.semantic.chroma_store import ChromaStore
    from app.ai.ai_provider import generate
    from app.scoring.text_scorer import score_relevance, deduplicate_docs
    results = search_web(query, max_results=max_results)
    if not results: return {"error": "Не вдалося отримати результати пошуку."}
    if depth == "fast":
        docs = [{"title":r["title"],"url":r["url"],"domain":r["domain"],"snippet":r["snippet"],"full_text":None} for r in results]
    else:
        extracted = extract_content_parallel([r["url"] for r in results])
        docs = [{"title":r["title"],"url":r["url"],"domain":r["domain"],"snippet":r["snippet"],"full_text":extracted.get(r["url"])} for r in results]
    docs = deduplicate_docs(docs, threshold=0.72)
    texts = [(d["full_text"] or d["snippet"] or d["title"]) for d in docs]
    doc_emb = create_embeddings_batch(texts); query_emb = create_embedding(query)
    store = ChromaStore(); store.add_documents(doc_emb, docs, query)
    k = 3 if depth=="fast" else 5 if depth=="standard" else 8
    top = store.search(query_emb, k=k)
    for d in top: d["_relevance"] = score_relevance(d.get("full_text") or d.get("snippet") or "", query)
    top.sort(key=lambda d: d.get("_relevance",0), reverse=True)
    context = "\n\n".join(f"[{i}] {d['title']}\nURL: {d['url']}\n{d.get('full_text') or d.get('snippet') or ''}" for i,d in enumerate(top,1))
    lang_labels = {
        "auto": "мовою запиту користувача",
        "ru": "російською мовою",
        "uk": "українською мовою",
        "en": "англійською мовою",
    }
    lang_hint = f"\n\nМова відповіді: {lang_labels.get(lang, lang_labels['auto'])}."

    raw = generate(
        api_key,
        f'Запит: "{query}"{lang_hint}\n\nМатеріали:\n{context}',
        lang=lang,
    )
    raw = re.sub(r"```json|```","",raw).strip()
    m = re.search(r"\{[\s\S]*\}",raw)
    if not m: return {"error":"Модель не повернула JSON","raw":raw[:400]}
    data = json.loads(m.group(0))
    sent = data.get("sentiment",{}); total_s = sent.get("positive",0)+sent.get("negative",0)+sent.get("neutral",0)
    if total_s > 0 and abs(total_s-1.0) > 0.05:
        for k2 in ("positive","negative","neutral"): sent[k2] = round(sent.get(k2,0)/total_s,3)
    data["sentiment"] = sent
    if not data.get("sources"):
        data["sources"] = [{"title":d["title"],"url":d["url"],"domain":d["domain"]} for d in top]
    save_cache(query, data, depth=depth, lang=lang)
    data["id"] = database.save_search(query, data, user_id, depth, lang)
    data["sources_used"] = len(top)
    return data
