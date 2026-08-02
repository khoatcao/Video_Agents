"""
Web search tool backed by DuckDuckGo — no API key required.

Exposed as a LangChain @tool so it can be bound to any LangChain agent
or passed into a LangGraph node directly.
"""

from __future__ import annotations

import logging

from duckduckgo_search import DDGS
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def search_trending_ai_topics(query: str, max_results: int = 5) -> str:
    """
    Search the web for recent AI and tech articles using DuckDuckGo.

    Use this tool to find trending topics, research a specific concept, or
    gather context before writing a video script.

    Args:
        query:       Natural-language search query (English or Vietnamese).
        max_results: Number of results to return (1–10, default 5).

    Returns:
        A formatted string with each result on its own block containing
        title, URL, and a brief content excerpt.
    """
    max_results = max(1, min(max_results, 10))

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        logger.error("DuckDuckGo search failed for query %r: %s", query, exc)
        return f"Search failed: {exc}"

    if not results:
        return "No results found."

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

    return "\n\n".join(lines)
