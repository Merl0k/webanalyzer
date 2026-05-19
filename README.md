# WebAnalyzer — Веб-сервіс збору та аналізу інформації

Дипломний проект. Веб-сервіс автоматично збирає інформацію з інтернет-джерел та проводить повний AI-аналіз: суммаризація, сентимент-аналіз, ключові факти, семантичне ранжування.

## Архітектура — Hybrid AI Search Pipeline

```
User Query
    ↓
Search API (DuckDuckGo)          ← duckduckgo_search + HTML fallback
    ↓
Content Extraction (async)       ← aiohttp + trafilatura (паралельно)
    ↓
C-accelerated Deduplication      ← scorer.c (Jaccard similarity, ctypes)
    ↓
Embeddings                       ← sentence-transformers (all-MiniLM-L6-v2)
    ↓
Vector Similarity (ChromaDB)     ← persistent semantic ranking top-5
    ↓
C-accelerated Relevance Scoring  ← scorer.c (term coverage + density)
    ↓
AI Analysis                      ← Groq / Gemini / Ollama (auto-detect)
    ↓
Celery Task Queue                ← async background processing
    ↓
SSE Streaming                    ← live progress → frontend
    ↓
PostgreSQL + Redis Cache
    ↓
REST API → Nginx → Frontend
```

## Стек технологій

| Шар | Технологія | Нотатки |
|-----|-----------|---------|
| Backend | Python 3.11, Flask | REST API + SSE |
| Task Queue | Celery + Redis | async pipeline |
| AI | Groq (llama-3.3-70b) / Gemini 2.0 / Ollama | auto-detect |
| Search | duckduckgo_search + HTML fallback | 2 стратегії |
| Extraction | aiohttp + trafilatura | паралельне |
| Semantic | sentence-transformers + ChromaDB | persistent vectors |
| C Extension | scorer.c → scorer.so | швидкий text scoring |
| Database | PostgreSQL (prod) / SQLite (dev) | SQLAlchemy ORM |
| Cache | Redis (TTL 1 год) | graceful fallback |
| Security | flask-limiter (10 req/min) | rate limiting |
| Logging | loguru | ротація 10MB |
| DevOps | Docker + Docker Compose | 5 сервісів |
| Monitoring | Flower | Celery dashboard |
| Frontend | Vanilla JS + SSE | live progress |
| Tests | pytest | 20+ тестів |

## Структура проекту

```
project/
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── build_scorer.sh          ← компіляція C розширення
│   ├── .env.example
│   │
│   ├── app/
│   │   ├── routes.py            ← REST API + SSE stream
│   │   │
│   │   ├── search/
│   │   │   ├── duckduckgo_search.py   ← 2 стратегії пошуку
│   │   │   └── content_extractor.py  ← async parallel
│   │   │
│   │   ├── ai/
│   │   │   ├── ai_provider.py   ← Groq/Gemini/Ollama
│   │   │   └── analyzer.py
│   │   │
│   │   ├── semantic/
│   │   │   ├── embeddings.py    ← sentence-transformers
│   │   │   ├── chroma_store.py  ← ChromaDB (persistent)
│   │   │   └── vector_store.py  ← FAISS fallback
│   │   │
│   │   ├── scoring/
│   │   │   ├── scorer.c         ← C extension source
│   │   │   ├── scorer.so        ← compiled (auto on Docker build)
│   │   │   └── text_scorer.py   ← Python wrapper + fallback
│   │   │
│   │   ├── tasks/
│   │   │   └── pipeline_task.py ← Celery task + SSE progress
│   │   │
│   │   ├── database/
│   │   │   ├── models.py
│   │   │   └── db.py            ← PostgreSQL + SQLite support
│   │   │
│   │   ├── cache/
│   │   │   └── redis_cache.py
│   │   │
│   │   └── utils/
│   │       └── helpers.py
│   │
│   └── tests/
│       ├── conftest.py
│       └── test_pipeline.py     ← 20+ тестів
│
├── frontend/
│   ├── index.html
│   ├── history.html
│   ├── stats.html
│   ├── css/style.css
│   └── js/
│       ├── app.js               ← SSE streaming + pipeline UI
│       ├── history.js
│       └── stats.js
│
├── docker-compose.yml           ← 5 сервісів
├── nginx.conf
└── README.md
```

## Швидкий старт

### Docker (рекомендовано)

```bash
docker compose up --build

# Frontend:   http://localhost:8080
# Backend:    http://localhost:5000
# Flower:     http://localhost:5555   (Celery monitoring)
```

### Локально (без Docker)

```bash
# 1. Скомпілювати C розширення
cd backend
bash build_scorer.sh

# 2. Встановити залежності
pip install -r requirements.txt

# 3. Запустити Redis (потрібен для Celery)
redis-server &

# 4. Запустити Celery worker
celery -A app.tasks.pipeline_task.celery_app worker --loglevel=info &

# 5. Запустити Flask
python app.py

# 6. Відкрити frontend
cd ../frontend && python -m http.server 8080
```

### Тести

```bash
cd backend
pytest tests/ -v
```

## API

| Метод | Шлях | Опис |
|-------|------|------|
| POST | `/api/analyze` | Запустити аналіз `{query, api_key}` |
| GET | `/api/task/<id>` | Статус Celery завдання |
| GET | `/api/stream/<id>` | SSE прогрес в реальному часі |
| GET | `/api/history` | Список запитів |
| GET | `/api/history/<id>` | Деталі запиту |
| DELETE | `/api/history/<id>` | Видалення |
| GET | `/api/stats` | Статистика |
| GET | `/api/health` | Health check (DB + Redis) |

## AI провайдери

| Провайдер | Формат ключа | Де отримати |
|-----------|-------------|-------------|
| Groq (безкоштовно) | `gsk_...` | console.groq.com |
| Gemini | будь-який інший | aistudio.google.com |
| Ollama (локально) | `ollama` | ollama.com |
