"""Shared pytest fixtures for WebAnalyzer backend tests."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


TEST_FERNET_KEY = "j9eXxJUIPO3ab5jUVXM-Jap_l1PQ79y6yz2_05uoaXo="


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    """
    Create a Flask app backed by isolated SQLite database.

    These tests do not use real PostgreSQL, Redis, Celery workers,
    DuckDuckGo, Gemini, Groq or Ollama.
    """
    db_path = tmp_path_factory.mktemp("db") / "test_webanalyzer.db"

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["JWT_SECRET"] = "pytest-jwt-secret"
    os.environ["ENCRYPTION_KEY"] = TEST_FERNET_KEY
    os.environ["REDIS_URL"] = "redis://localhost:6379/15"
    os.environ["FLASK_ENV"] = "testing"

    # Import after env variables are set.
    import importlib
    import app.database.db as db_mod
    import app as app_pkg

    importlib.reload(db_mod)
    importlib.reload(app_pkg)

    flask_app = app_pkg.create_app()
    
    flask_app.config.update(
    TESTING=True,
    RATELIMIT_ENABLED=False,
)

   # Flask-Limiter is already initialized inside create_app(),
# so config alone may be too late. Disable it explicitly for tests.
    try:
        app_pkg.limiter.enabled = False
    except Exception:
        pass

    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def register_and_login(client, email: str | None = None, password: str = "StrongPass123"):
    email = email or f"pytest+{secrets.token_hex(6)}@example.com"

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )

    assert reg.status_code == 201, reg.get_data(as_text=True)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert login.status_code == 200, login.get_data(as_text=True)

    return login.get_json()["user"]


@pytest.fixture()
def auth_client(client):
    user = register_and_login(client)
    return client, user


def sample_result(summary: str = "Тестове резюме"):
    return {
        "summary": summary,
        "sentiment": {
            "overall": "positive",
            "positive": 0.7,
            "negative": 0.1,
            "neutral": 0.2,
            "explanation": "Переважно позитивна тональність.",
        },
        "key_facts": [
            "Факт 1",
            "Факт 2",
            "Факт 3",
        ],
        "sources": [
            {
                "title": "Example source",
                "url": "https://example.com/article",
                "domain": "example.com",
            }
        ],
    }


def create_saved_search(user_id: int, query: str = "Тестовий запит"):
    from app.database import db as database

    return database.save_search(
        query=query,
        result=sample_result(),
        user_id=user_id,
        depth="standard",
        lang="uk",
    )