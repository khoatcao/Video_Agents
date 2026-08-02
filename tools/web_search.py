"""
Web search tool backed by Tavily.

Exposed as a LangChain @tool so it can be bound to any LangChain agent
or passed into a LangGraph node directly.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool
from tavily import TavilyClient

from config.settings import TAVILY_API_KEY

logger = logging.getLogger(__name__)

_client: Optional[TavilyClient] = None


def _get_client() -> TavilyClient:
    """Lazily initialise and cache the Tavily client."""
    global _client
    if _client is None:
        _client = TavilyClient(api_key=TAVILY_API_KEY)
    return _client


@tool
def search_trending_ai_topics(query: str, max_results: int = 5) -> str:
    """
    Search the web for recent AI and tech articles using Tavily.

    Use this tool to find trending topics, research a specific concept, or
    gather context before writing a video script.

    Args:
        query:       Natural-language search query (English or Vietnamese).
        max_results: Number of results to return (1–10, default 5).

    Returns:
        A formatted string with each result on its own block containing
        title, URL, published date, and a brief content excerpt.
    """
    max_results = max(1, min(max_results, 10))

    try:
        client = _get_client()
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
            include_raw_content=False,
        )
    except Exception as exc:
        logger.error("Tavily search failed for query %r: %s", query, exc)
        return f"Search failed: {exc}"

    lines: list[str] = []

    if response.get("answer"):
        lines.append(f"Summary: {response['answer']}\n")

    results: list[dict] = response.get("results", [])
    if not results:
        return "No results found."

    for idx, result in enumerate(results, start=1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        published = result.get("published_date", "")
        content = result.get("content", "")

        # Trim long excerpts
        if len(content) > 400:
            content = content[:397] + "..."

        block = [f"[{idx}] {title}"]
        if published:
            block.append(f"    Date: {published}")
        block.append(f"    URL:  {url}")
        if content:
            block.append(f"    {content}")
        lines.append("\n".join(block))

    return "\n\n".join(lines)
