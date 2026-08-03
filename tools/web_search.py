"""
Web search tool backed by RSS feeds — no API key, no rate limits.

Fetches from a curated list of AI/tech RSS feeds (English + Vietnamese),
filters by keyword relevance, and returns the most recent matching articles.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import feedparser
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Curated RSS feeds — AI/tech news (English) + Vietnamese tech
_RSS_FEEDS = [
    # English AI/tech
    ("Hacker News",         "https://hnrss.org/frontpage"),
    ("TechCrunch AI",       "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI",        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("MIT Tech Review",     "https://www.technologyreview.com/feed/"),
    ("VentureBeat AI",      "https://venturebeat.com/category/ai/feed/"),
    ("ZDNet AI",            "https://www.zdnet.com/topic/artificial-intelligence/rss.xml"),
    ("Wired AI",            "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("Google News AI",      "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en"),
    # Vietnamese tech
    ("VnExpress Công nghệ", "https://vnexpress.net/rss/so-hoa.rss"),
    ("VnExpress Khoa học",  "https://vnexpress.net/rss/khoa-hoc.rss"),
    ("Tuoi Tre Công nghệ",  "https://tuoitre.vn/rss/nhip-song-so.rss"),
    ("Thanh Niên Công nghệ","https://thanhnien.vn/rss/cong-nghe.rss"),
]

_FETCH_TIMEOUT = 10   # seconds per feed
_MAX_AGE_DAYS  = 7    # ignore articles older than this


def _fetch_feed(name: str, url: str) -> list[dict]:
    """Fetch one RSS feed and return a list of normalised article dicts."""
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        articles = []
        now = time.time()

        for entry in feed.entries:
            # Parse publish time
            published_ts: Optional[float] = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_ts = time.mktime(entry.published_parsed)
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published_ts = time.mktime(entry.updated_parsed)

            # Skip old articles
            if published_ts and (now - published_ts) > _MAX_AGE_DAYS * 86400:
                continue

            title   = getattr(entry, "title",   "").strip()
            summary = getattr(entry, "summary", "").strip()
            link    = getattr(entry, "link",    "").strip()

            if not title:
                continue

            # Strip HTML tags from summary
            import re
            summary = re.sub(r"<[^>]+>", "", summary)[:300]

            articles.append({
                "source":    name,
                "title":     title,
                "summary":   summary,
                "url":       link,
                "published": published_ts or 0.0,
            })

        return articles
    except Exception as exc:
        logger.debug("Failed to fetch feed %r: %s", name, exc)
        return []


def _score_article(article: dict, keywords: list[str]) -> int:
    """Score an article by how many keywords appear in title + summary."""
    text = (article["title"] + " " + article["summary"]).lower()
    return sum(1 for kw in keywords if kw.lower() in text)


def _fetch_all_feeds(max_workers: int = 6) -> list[dict]:
    """Fetch all feeds in parallel and return combined article list."""
    all_articles: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_feed, name, url): name for name, url in _RSS_FEEDS}
        for future in as_completed(futures):
            all_articles.extend(future.result())
    return all_articles


@tool
def search_trending_ai_topics(query: str, max_results: int = 5) -> str:
    """
    Search trending AI and tech news from RSS feeds — no API key required.

    Fetches from Hacker News, TechCrunch, The Verge, MIT Tech Review,
    VentureBeat, VnExpress, and Tuoi Tre in parallel. Filters and ranks
    articles by keyword relevance and recency.

    Args:
        query:       Keywords to filter articles (English or Vietnamese).
        max_results: Number of articles to return (default 5).

    Returns:
        Formatted string with title, source, URL, and summary per article.
    """
    max_results = max(1, min(max_results, 10))
    keywords = query.lower().split()

    logger.info("Fetching RSS feeds for query: %r", query)
    articles = _fetch_all_feeds()

    if not articles:
        logger.warning("All RSS feeds returned no articles.")
        return "No articles found — RSS feeds may be temporarily unavailable."

    # Score and sort: first by keyword relevance, then by recency
    scored = [(a, _score_article(a, keywords)) for a in articles]
    scored.sort(key=lambda x: (x[1], x[0]["published"]), reverse=True)

    # Take top results (prefer articles with at least 1 keyword match)
    top = [a for a, score in scored if score > 0][:max_results]
    if not top:
        # Fall back to most recent articles if no keyword matches
        top = sorted(articles, key=lambda a: a["published"], reverse=True)[:max_results]
        logger.info("No keyword matches — returning %d most recent articles.", len(top))
    else:
        logger.info("Found %d relevant articles out of %d total.", len(top), len(articles))

    lines: list[str] = []
    for idx, article in enumerate(top, start=1):
        published = (
            datetime.fromtimestamp(article["published"]).strftime("%Y-%m-%d")
            if article["published"]
            else "unknown date"
        )
        block = [
            f"[{idx}] {article['title']}",
            f"    Source: {article['source']} — {published}",
            f"    URL:    {article['url']}",
        ]
        if article["summary"]:
            block.append(f"    {article['summary']}")
        lines.append("\n".join(block))

    return "\n\n".join(lines)
