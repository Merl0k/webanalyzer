import re
import requests
from urllib.parse import urlparse
from loguru import logger


def _parse_domain(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def search_web(query: str, max_results: int = 10) -> list:
    """Search the web using DuckDuckGo with multiple fallback strategies."""
    results = []

    # Strategy 1: duckduckgo_search library
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            for r in list(ddgs.text(query, max_results=max_results)):
                url = r.get("href") or r.get("url") or ""
                results.append({
                    "title":   r.get("title", ""),
                    "url":     url,
                    "domain":  _parse_domain(url),
                    "snippet": (r.get("body") or r.get("snippet") or "")[:400],
                })
        if results:
            logger.info(f"DDG library returned {len(results)} results")
            return results
    except Exception as e:
        logger.warning(f"DDG library failed: {e}")

    # Strategy 2: DDG HTML fallback
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "kl": "ua-uk"},
            headers=headers,
            timeout=10,
        )
        html = resp.text
        blocks = re.findall(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
        snips  = re.findall(r'class="result__snippet"[^>]*>(.*?)</span>', html, re.S)
        for i, (url, title) in enumerate(blocks[:max_results]):
            if "duckduckgo.com/l/?uddg=" in url:
                import urllib.parse as up
                url = up.unquote(up.parse_qs(url.split("?", 1)[1]).get("uddg", [""])[0])
            if not url.startswith("http"):
                continue
            snip = re.sub(r'<[^>]+>', '', snips[i]).strip() if i < len(snips) else ""
            results.append({
                "title":   re.sub(r'<[^>]+>', '', title).strip(),
                "url":     url,
                "domain":  _parse_domain(url),
                "snippet": snip[:400],
            })
        if results:
            logger.info(f"DDG HTML fallback returned {len(results)} results")
            return results
    except Exception as e:
        logger.error(f"DDG HTML fallback failed: {e}")

    logger.error("All search strategies failed")
    return results
