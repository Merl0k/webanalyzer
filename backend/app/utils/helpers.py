"""
app/utils/helpers.py

Shared utility functions across the application.
"""
import re
from urllib.parse import urlparse
from datetime import datetime


def parse_domain(url: str) -> str:
    """Extract domain from URL safely."""
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def truncate(text: str, max_len: int = 1500) -> str:
    """Truncate text to max_len characters."""
    if not text:
        return ""
    return text[:max_len]


def clean_json_response(raw: str) -> str:
    """Strip markdown code fences from AI JSON response."""
    return re.sub(r"```json|```", "", raw).strip()


def extract_json(raw: str) -> str | None:
    """Find the first JSON object in a string."""
    match = re.search(r"\{[\s\S]*\}", raw)
    return match.group(0) if match else None


def normalize_sentiment(sent: dict) -> dict:
    """Ensure positive + negative + neutral = 1.0."""
    total = sent.get("positive", 0) + sent.get("negative", 0) + sent.get("neutral", 0)
    if total > 0 and abs(total - 1.0) > 0.05:
        for k in ("positive", "negative", "neutral"):
            sent[k] = round(sent.get(k, 0) / total, 3)
    return sent


def format_datetime(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")
