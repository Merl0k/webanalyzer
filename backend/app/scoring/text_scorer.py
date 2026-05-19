"""
app/scoring/text_scorer.py

Python wrapper around the C shared library (scorer.so).
Falls back to pure-Python implementation if the .so is not compiled yet.
"""
import ctypes
import os
from loguru import logger

_lib = None
_LIB_PATH = os.path.join(os.path.dirname(__file__), "scorer.so")


def _load_lib():
    global _lib
    if _lib is not None:
        return _lib
    if os.path.exists(_LIB_PATH):
        try:
            _lib = ctypes.CDLL(_LIB_PATH)
            _lib.score_relevance.restype = ctypes.c_float
            _lib.score_relevance.argtypes = [
                ctypes.c_char_p, ctypes.c_char_p,
                ctypes.c_int,    ctypes.c_int,
            ]
            _lib.jaccard_similarity.restype = ctypes.c_float
            _lib.jaccard_similarity.argtypes = [
                ctypes.c_char_p, ctypes.c_char_p,
                ctypes.c_int,    ctypes.c_int,
            ]
            logger.info("C scorer loaded (scorer.so)")
        except Exception as e:
            logger.warning(f"Could not load scorer.so: {e} — using Python fallback")
            _lib = None
    return _lib


# ── Pure-Python fallback ────────────────────────────────────────────

def _py_score_relevance(text: str, query: str) -> float:
    if not text or not query:
        return 0.0
    t_words = set(text.lower().split())
    q_words = set(query.lower().split())
    if not q_words:
        return 0.0
    matched = len(t_words & q_words)
    coverage = matched / len(q_words)
    density = matched / max(len(t_words), 1)
    return round(0.65 * coverage + 0.25 * density, 4)


def _py_jaccard(a: str, b: str) -> float:
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


# ── Public API ──────────────────────────────────────────────────────

def score_relevance(text: str, query: str) -> float:
    """Score how relevant `text` is to `query`. Returns 0.0–1.0."""
    lib = _load_lib()
    if lib is not None:
        tb = text.encode("utf-8", errors="replace")
        qb = query.encode("utf-8", errors="replace")
        return lib.score_relevance(tb, qb, len(tb), len(qb))
    return _py_score_relevance(text, query)


def jaccard_similarity(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two texts. Returns 0.0–1.0."""
    lib = _load_lib()
    if lib is not None:
        ab = a.encode("utf-8", errors="replace")
        bb = b.encode("utf-8", errors="replace")
        return lib.jaccard_similarity(ab, bb, len(ab), len(bb))
    return _py_jaccard(a, b)


def deduplicate_docs(docs: list[dict], threshold: float = 0.72) -> list[dict]:
    """
    Remove near-duplicate documents based on Jaccard similarity of their content.
    Keeps the first seen document when duplicates are detected.
    """
    unique = []
    for doc in docs:
        text = doc.get("full_text") or doc.get("snippet") or ""
        is_dup = False
        for kept in unique:
            ref = kept.get("full_text") or kept.get("snippet") or ""
            if jaccard_similarity(text, ref) >= threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(doc)
    logger.debug(f"Dedup: {len(docs)} → {len(unique)} docs")
    return unique
