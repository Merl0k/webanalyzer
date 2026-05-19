import asyncio
import aiohttp
import trafilatura
from loguru import logger

MAX_CONTENT_LEN = 1500
FETCH_TIMEOUT = 8


async def _fetch_and_extract(session: aiohttp.ClientSession, url: str) -> str | None:
    """Fetch a URL and extract clean text using trafilatura."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT)) as resp:
            if resp.status != 200:
                return None
            html = await resp.text(errors="replace")
            text = trafilatura.extract(html)
            if text:
                return text[:MAX_CONTENT_LEN]
            return None
    except Exception as e:
        logger.debug(f"Content extraction failed for {url}: {e}")
        return None


async def extract_all_async(urls: list[str]) -> dict[str, str | None]:
    """Extract content from multiple URLs in parallel."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
        "Accept-Language": "uk,en;q=0.9",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [_fetch_and_extract(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
    return {url: text for url, text in zip(urls, results)}


def extract_content_parallel(urls: list[str]) -> dict[str, str | None]:
    """Synchronous wrapper for async parallel extraction."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, extract_all_async(urls))
                return future.result(timeout=30)
        return loop.run_until_complete(extract_all_async(urls))
    except Exception as e:
        logger.error(f"Parallel extraction failed: {e}")
        return {url: None for url in urls}
