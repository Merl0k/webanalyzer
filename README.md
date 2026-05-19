# WebAnalyzer v3

**WebAnalyzer v3** — вебзастосунок для автоматичного збору, аналізу, збереження та візуалізації інформації з веб-джерел.

Проєкт реалізований як дипломна робота і демонструє повний цикл роботи інформаційної системи: авторизація користувачів, безпечне збереження API-ключів, пошук інформації, AI-аналіз, історія результатів, експорт, публічні посилання, статистика та API-документація.

---

## Основні можливості

- Реєстрація та авторизація користувачів.
- JWT access token + refresh token.
- httpOnly cookie для безпечного зберігання токенів.
- bcrypt-хешування паролів.
- Зашифроване зберігання API-ключів через Fernet.
- Підтримка AI-провайдерів:
  - Gemini;
  - Groq;
  - Ollama.
- Вибір глибини аналізу:
  - Fast;
  - Standard;
  - Deep.
- Вибір мови відповіді:
  - auto;
  - ru;
  - uk;
  - en.
- Фоновий аналіз через Celery worker.
- Redis для черг, кешу та прогресу задач.
- PostgreSQL для збереження користувачів, історії, тегів та колекцій.
- Історія аналізів.
- Теги для результатів.
- Фільтрація історії за тегами.
- Порівняння 2–3 результатів.
- Візуалізація тональності через donut chart.
- Статистика користувача.
- Експорт результатів:
  - JSON;
  - Markdown;
  - PDF.
- Публічні share-посилання.
- Swagger/OpenAPI документація.
- Docker Compose запуск.
- Pytest-тести.
- GitHub Actions CI.

---

## Архітектура

Проєкт складається з декількох сервісів:

```text
frontend  → nginx + HTML/CSS/JS
web       → Flask API
worker    → Celery worker
flower    → Celery monitoring
postgres  → PostgreSQL database
redis     → Redis broker/cache
```

Схема роботи аналізу:

```text
Користувач вводить запит
        ↓
Frontend надсилає POST /api/v1/analyze
        ↓
Flask створює Celery task
        ↓
Worker виконує пошук і збір джерел
        ↓
AI-провайдер формує аналіз
        ↓
Результат зберігається в PostgreSQL
        ↓
Frontend отримує результат через SSE / polling
```

---

## Стек технологій

### Backend

- Python 3.11
- Flask
- SQLAlchemy
- PostgreSQL
- Redis
- Celery
- bcrypt
- PyJWT
- cryptography / Fernet
- ReportLab
- Loguru
- Pytest

### AI / Analysis

- Gemini API
- Groq API
- Ollama
- DuckDuckGo Search
- ChromaDB
- sentence-transformers
- semantic ranking

### Frontend

- HTML
- CSS
- Vanilla JavaScript
- Chart.js
- Tabler Icons
- Nginx

### DevOps

- Docker
- Docker Compose
- GitHub Actions
- Swagger/OpenAPI

---

## Структура проєкту

```text
webanalyzer_v3/
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   ├── auth/
│   │   ├── cache/
│   │   ├── database/
│   │   ├── export/
│   │   ├── scoring/
│   │   ├── search/
│   │   ├── semantic/
│   │   ├── tasks/
│   │   └── routes.py
│   ├── migrations/
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── requirements-test.txt
├── frontend/
│   ├── css/
│   ├── js/
│   ├── index.html
│   ├── auth.html
│   ├── history.html
│   ├── profile.html
│   └── stats.html
├── .github/
│   └── workflows/
├── docker-compose.yml
├── nginx.conf
├── README.md
└── plam.md
```

---

## Запуск через Docker

### 1. Клонувати проєкт

```bash
git clone https://github.com/YOUR_USERNAME/webanalyzer_v3.git
cd webanalyzer_v3
```

### 2. Створити `.env`

У корені проєкту потрібно створити файл:

```text
.env
```

Приклад:

```env
JWT_SECRET=your-generated-jwt-secret
ENCRYPTION_KEY=your-generated-fernet-key
```

Згенерувати `JWT_SECRET`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Згенерувати `ENCRYPTION_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Запустити Docker Compose

```bash
docker compose up --build
```

Або у фоні:

```bash
docker compose up -d --build
```

---

## Адреси сервісів

Frontend:

```text
http://localhost:8080
```

Backend API:

```text
http://localhost:5000/api/v1
```

Swagger/OpenAPI:

```text
http://localhost:8080/api/v1/docs
http://localhost:8080/api/v1/openapi.json
```

Flower:

```text
http://localhost:5555
```

Health check:

```text
http://localhost:8080/api/v1/health
```

---

## Основні API endpoints

### Auth

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/logout
POST /api/v1/auth/refresh
GET  /api/v1/auth/me
```

### Profile

```text
GET    /api/v1/profile/keys
POST   /api/v1/profile/keys
DELETE /api/v1/profile/keys/<provider>
POST   /api/v1/profile/theme
```

### Analysis

```text
POST /api/v1/analyze
GET  /api/v1/task/<task_id>
GET  /api/v1/stream/<task_id>
```

### History

```text
GET    /api/v1/history
GET    /api/v1/history/<id>
DELETE /api/v1/history/<id>
```

### Export

```text
GET /api/v1/history/<id>/export/json
GET /api/v1/history/<id>/export/markdown
GET /api/v1/history/<id>/export/pdf
```

### Share

```text
POST /api/v1/history/<id>/share
GET  /api/v1/share/<token>
```

### Tags

```text
GET    /api/v1/tags
POST   /api/v1/tags
DELETE /api/v1/tags/<tag_id>
POST   /api/v1/history/<search_id>/tags/<tag_id>
DELETE /api/v1/history/<search_id>/tags/<tag_id>
```

### Collections

```text
GET  /api/v1/collections
POST /api/v1/collections
POST /api/v1/collections/<collection_id>/add/<search_id>
```

### Compare

```text
POST /api/v1/compare
```

### Stats

```text
GET /api/v1/stats
```

---

## AI-провайдери

У профілі користувач може додати API-ключ.

Провайдер визначається автоматично:

```text
gsk_...  → Groq
ollama   → Ollama
інше     → Gemini
```

API-ключі зберігаються у базі даних у зашифрованому вигляді через Fernet.

---

## Режими аналізу

### Fast

Швидкий режим. Використовує менше джерел і працює швидше.

### Standard

Основний режим. Баланс між швидкістю та якістю.

### Deep

Глибший аналіз із більшою кількістю джерел.

---

## Мови відповіді

Користувач може вибрати мову відповіді:

```text
auto — автоматично, мовою запиту
ru   — російська
uk   — українська
en   — англійська
```

---

## Експорт

Результати аналізу можна експортувати у форматах:

```text
JSON
Markdown
PDF
```

PDF генерується через `ReportLab`, що дозволяє стабільно створювати PDF у Docker без залежності від HTML/CSS-рендерингу.

---

## Тести

Для тестів використовується окремий легкий набір залежностей:

```text
backend/requirements-test.txt
```

Запуск тестів:

```bash
cd backend
python -m pip install -r requirements-test.txt
python -m pytest -q
```

Очікуваний результат:

```text
15 passed
```

Тести перевіряють:

- health endpoint;
- OpenAPI JSON;
- реєстрацію;
- логін;
- logout;
- профіль;
- API-ключі;
- історію;
- експорт JSON / Markdown / PDF;
- share links;
- compare;
- tags;
- захист від доступу до чужих результатів.

---

## GitHub Actions

У проєкті налаштовано CI:

```text
.github/workflows/backend-ci.yml
```

CI автоматично запускає backend-тести при:

```text
push
pull_request
```

Docker build винесений у ручний запуск через `workflow_dispatch`, щоб не перевантажувати CI важкими AI-залежностями.

---

## Безпека

У проєкті реалізовано:

- bcrypt-хешування паролів;
- JWT access token;
- refresh token;
- httpOnly cookie;
- Fernet-шифрування API-ключів;
- перевірка власника результату;
- заборона доступу до чужої історії;
- захищений export/share/compare;
- `.env` не додається у Git;
- Docker context очищений через `.dockerignore`.

---

## Docker optimization

Для зменшення розміру Docker image використовується:

- `.dockerignore`;
- один спільний backend image для web/worker/flower;
- виключення `.venv`, `venv`, логів, локальних баз і кешів із Docker context;
- окремий `requirements-test.txt` для тестів.

---

## Реалізовано по ТЗ

| Функція | Статус |
|---|---|
| Реєстрація / авторизація | ✅ |
| JWT + refresh token | ✅ |
| httpOnly cookie | ✅ |
| bcrypt | ✅ |
| Fernet encryption | ✅ |
| AI-провайдери Gemini / Groq / Ollama | ✅ |
| Fast / Standard / Deep | ✅ |
| Вибір мови відповіді | ✅ |
| Celery worker | ✅ |
| Redis | ✅ |
| PostgreSQL | ✅ |
| Історія аналізів | ✅ |
| Export JSON / Markdown / PDF | ✅ |
| Share links | ✅ |
| Tags | ✅ |
| Compare UI | ✅ |
| Donut chart | ✅ |
| Stats page | ✅ |
| Swagger/OpenAPI | ✅ |
| Docker Compose | ✅ |
| Pytest tests | ✅ |
| GitHub Actions | ✅ |

---

## Можливості для подальшого розвитку

У майбутньому можна додати:

- timeline тональності;
- word cloud;
- граф джерел через D3.js;
- автодоповнення запитів з історії;
- повторний аналіз із diff;
- повноцінний dashboard статистики;
- structlog / JSON logging;
- production WSGI server замість Flask dev server;
- розділення runtime-залежностей web і worker;
- більш глибоку систему колекцій.

---

## Автор

Дипломний проєкт: **WebAnalyzer**

Тема: **Вебсервіс для автоматичного збору та аналізу інформації з різних веб-джерел**.