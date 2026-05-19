"""Lightweight unit tests for helper modules."""

from __future__ import annotations


def test_detect_provider_groq():
    from app.ai.ai_provider import detect_provider

    assert detect_provider("gsk_abc123") == "groq"


def test_detect_provider_ollama():
    from app.ai.ai_provider import detect_provider

    assert detect_provider("ollama") == "ollama"
    assert detect_provider("OLLAMA") == "ollama"


def test_detect_provider_gemini():
    from app.ai.ai_provider import detect_provider

    assert detect_provider("AIzaSy_anything") == "gemini"
    assert detect_provider("random_key") == "gemini"


def test_build_system_prompt_lang_ru():
    from app.ai.ai_provider import build_system_prompt

    prompt = build_system_prompt("ru")

    assert "Russian" in prompt
    assert "Return ONLY valid JSON" in prompt


def test_score_relevance_empty_inputs():
    from app.scoring.text_scorer import score_relevance

    assert score_relevance("", "query") == 0.0
    assert score_relevance("text", "") == 0.0
    assert score_relevance("", "") == 0.0


def test_jaccard_similarity_identical():
    from app.scoring.text_scorer import jaccard_similarity

    sim = jaccard_similarity("hello world foo bar", "hello world foo bar")

    assert sim >= 0.99


def test_deduplicate_docs_removes_duplicate():
    from app.scoring.text_scorer import deduplicate_docs

    docs = [
        {
            "title": "A",
            "url": "https://a.example",
            "snippet": "python programming tutorial basics",
        },
        {
            "title": "B",
            "url": "https://b.example",
            "snippet": "python programming tutorial basics",
        },
        {
            "title": "C",
            "url": "https://c.example",
            "snippet": "quantum computing qubits physics",
        },
    ]

    result = deduplicate_docs(docs, threshold=0.6)

    assert len(result) == 2