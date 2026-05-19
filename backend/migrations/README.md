Alembic migrations for WebAnalyzer backend.

Usage:

1. Install dependencies (ensure `alembic` is in `requirements.txt`):

```
pip install -r requirements.txt
```

2. Initialize (already present) and create an autogenerate migration:

```
cd backend
alembic revision --autogenerate -m "init"
alembic upgrade head
```

The `env.py` is configured to import `app.database.models.Base` as the metadata target.
