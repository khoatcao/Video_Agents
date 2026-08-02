"""
Web search tool backed by DuckDuckGo — no API key required.

Includes retry logic with backoff and a news-search fallback to handle
DuckDuckGo rate limits reliably.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import RatelimitException
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAYS = [2, 5, 10]  # seconds between retries


def _ddg_text_with_retry(query: str, max_results: int) -> list[dict]:
    """Text search with retry + exponential backoff on rate limits."""
    for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=max_results,
                    region="vn-vi",
                    safesearch="off",
                ))
            if results:
                return results
        except RatelimitException:
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "DuckDuckGo rate limit on text search (attempt %d/%d) — retrying in %ds",
                    attempt, _MAX_RETRIES, delay,
                )
                time.sleep(delay)
            else:
                logger.warning("DuckDuckGo text search rate limited after %d attempts.", _MAX_RETRIES)
        except Exception as exc:
            logger.warning("DuckDuckGo text search error: %s", exc)
            break
    return []


def _ddg_news_fallback(query: str, max_results: int) -> list[dict]:
    """News search as fallback — different endpoint, less rate limited."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(
                query,
                max_results=max_results,
                region="vn-vi",
            ))
        # Normalise news results to same shape as text results
        normalised = []
        for r in results:
            normalised.append({
                "title": r.get("title", ""),
                "href": r.get("url", ""),
                "body": r.get("body", ""),
            })
        return normalised
    except Exception as exc:
        logger.warning("DuckDuckGo news fallback failed: %s", exc)
        return []


@tool
def search_trending_ai_topics(query: str, max_results: int = 5) -> str:
    """
    Search the web for recent AI and tech articles using DuckDuckGo.

    Retries up to 3 times on rate limits, then falls back to news search.

    Args:
        query:       Natural-language search query (English or Vietnamese).
        max_results: Number of results to return (1–10, default 5).

    Returns:
        A formatted string with each result on its own block containing
        title, URL, and a brief content excerpt.
    """
    max_results = max(1, min(max_results, 10))

    # Append current year to bias toward fresh results
    year = datetime.now().year
    full_query = f"{query} {year}"

    results = _ddg_text_with_retry(full_query, max_results)

    if not results:
        logger.info("Text search returned no results — trying news fallback.")
        results = _ddg_news_fallback(full_query, max_results)

    if not results:
        logger.error("All DuckDuckGo search methods failed for query %r", query)
        return f"Search unavailable for: {query}"

    lines: list[str] = []
    for idx, result in enumerate(results, start=1):
        title = result.get("title", "No title")
        url = result.get("href", "")
        content = result.get("body", "")

        if len(content) > 400:
            content = content[:397] + "..."

        block = [f"[{idx}] {title}"]
        block.append(f"    URL:  {url}")
        if content:
            block.append(f"    {content}")
        lines.append("\n".join(block))

    logger.info("DuckDuckGo returned %d results for %r", len(results), query)
    return "\n\n".join(lines)
