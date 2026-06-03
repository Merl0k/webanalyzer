import requests
from loguru import logger


LANG_NAMES = {
    "auto": "the same language as the user's query",
    "ru": "Russian",
    "uk": "Ukrainian",
    "en": "English",
}

GEMINI_DEFAULT_MODEL = "gemini-2.5-flash-lite"

GEMINI_ALLOWED_MODELS = {
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
}

GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

GROQ_ALLOWED_MODELS = {
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
}

OLLAMA_DEFAULT_MODEL = "qwen2.5:3b"


def build_system_prompt(lang: str = "auto") -> str:
    """
    Build system prompt for AI providers.
    lang:
      auto — answer in the same language as the user query
      ru   — Russian
      uk   — Ukrainian
      en   — English
    """
    lang = (lang or "auto").strip().lower()

    if lang not in LANG_NAMES:
        lang = "auto"

    language_rule = LANG_NAMES[lang]

    return f"""You are an analytical module for a web information analysis system.

Your task:
1. Read the user's query and provided web materials.
2. Create a concise analytical result.
3. Return ONLY valid JSON.
4. Do not use markdown fences.
5. Do not add explanations outside JSON.
6. The response language must be: {language_rule}.

Return JSON exactly with this structure:
{{
  "summary": "3-5 sentence summary",
  "sentiment": {{
    "overall": "positive|negative|neutral|mixed",
    "positive": 0.0,
    "negative": 0.0,
    "neutral": 0.0,
    "explanation": "short sentiment explanation"
  }},
  "key_facts": [
    "fact 1",
    "fact 2",
    "fact 3",
    "fact 4",
    "fact 5"
  ],
  "sources": [
    {{
      "title": "...",
      "url": "https://...",
      "domain": "..."
    }}
  ]
}}

Rules:
- positive + negative + neutral must equal 1.0.
- key_facts must contain 3-7 useful facts.
- sources must contain only sources that were actually provided in the materials.
- summary, explanation and key_facts must follow the selected response language.
"""


def detect_provider(api_key: str) -> str:
    key = (api_key or "").strip()

    if key.lower().startswith("ollama"):
        return "ollama"

    if key.startswith("gsk_"):
        return "groq"

    return "gemini"


def normalize_model(provider: str, model: str | None = None) -> str:
    """
    Normalize selected model.

    Important:
    old Gemini models like gemini-1.5-* and gemini-2.0-* are no longer safe,
    so they are automatically replaced with gemini-2.5-flash-lite.
    """
    model = (model or "").strip()

    if provider == "gemini":
        if model in GEMINI_ALLOWED_MODELS:
            return model

        return GEMINI_DEFAULT_MODEL

    if provider == "groq":
        if model in GROQ_ALLOWED_MODELS:
            return model

        return GROQ_DEFAULT_MODEL

    if provider == "ollama":
        return model or OLLAMA_DEFAULT_MODEL

    return model


def call_groq(
    api_key: str,
    user_message: str,
    system_prompt: str,
    model: str | None = None,
) -> str:
    model = normalize_model("groq", model)

    logger.info(f"Calling Groq API ({model})")

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 1500,
            "temperature": 0.2,
        },
        timeout=30,
    )

    resp.raise_for_status()

    return resp.json()["choices"][0]["message"]["content"]


def call_ollama(
    user_message: str,
    system_prompt: str,
    model: str | None = None,
) -> str:
    model = normalize_model("ollama", model)

    logger.info(f"Calling Ollama local model: {model}")

    resp = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=120,
    )

    resp.raise_for_status()

    return resp.json()["message"]["content"]


def call_gemini(
    api_key: str,
    user_message: str,
    system_prompt: str,
    model: str | None = None,
) -> str:
    model = normalize_model("gemini", model)

    logger.info(f"Calling Gemini API ({model})")

    import google.generativeai as genai

    genai.configure(api_key=api_key)

    gemini_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_prompt,
    )

    return gemini_model.generate_content(user_message).text


def generate(
    api_key: str,
    user_message: str,
    lang: str = "auto",
    model: str | None = None,
) -> str:
    """
    Route request to the correct AI provider based on API key.
    """
    provider = detect_provider(api_key)
    system_prompt = build_system_prompt(lang)
    model = normalize_model(provider, model)

    if provider == "groq":
        return call_groq(api_key, user_message, system_prompt, model=model)

    if provider == "ollama":
        return call_ollama(user_message, system_prompt, model=model)

    return call_gemini(api_key, user_message, system_prompt, model=model)