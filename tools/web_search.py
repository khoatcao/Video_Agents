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
    # AI infra & research
    ("NVIDIA Blog",         "https://blogs.nvidia.com/feed/"),
    ("Google AI Blog",      "https://blog.google/technology/ai/rss/"),
    ("AWS ML Blog",         "https://aws.amazon.com/blogs/machine-learning/feed/"),
    ("Hugging Face Blog",   "https://huggingface.co/blog/feed.xml"),
    ("OpenAI Blog",         "https://openai.com/blog/rss.xml"),
    ("OpenAI News",         "https://news.google.com/rss/search?q=OpenAI&hl=en-US&gl=US&ceid=US:en"),
    # Startup & business
    ("TechCrunch AI",       "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI",      "https://venturebeat.com/category/ai/feed/"),
    ("Wired AI",            "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("The Verge AI",        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    # Community & research
    ("Hacker News",         "https://hnrss.org/frontpage"),
    ("ZDNet AI",            "https://www.zdnet.com/topic/artificial-intelligence/rss.xml"),
    ("MIT Tech Review",     "https://www.technologyreview.com/feed/"),
    ("Google News AI",      "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en"),
    # Vietnamese tech
    ("VnExpress Công nghệ", "https://vnexpress.net/rss/so-hoa.rss"),
    ("VnExpress Khoa học",  "https://vnexpress.net/rss/khoa-hoc.rss"),
    ("Tuoi Tre Công nghệ",  "https://tuoitre.vn/rss/nhip-song-so.rss"),
    ("Thanh Niên Công nghệ","https://thanhnien.vn/rss/cong-nghe.rss"),
]

# Slot → which sources to pull from
_SLOT_SOURCES: dict[str, list[str]] = {
    "morning":   ["NVIDIA Blog", "Google AI Blog", "AWS ML Blog", "Hugging Face Blog", "OpenAI Blog", "OpenAI News"],
    "afternoon": ["TechCrunch AI", "VentureBeat AI", "Wired AI", "The Verge AI"],
    "evening":   ["Hacker News", "ZDNet AI", "MIT Tech Review", "Google News AI"],
    "night":     ["VnExpress Công nghệ", "VnExpress Khoa học", "Tuoi Tre Công nghệ", "Thanh Niên Công nghệ"],
}

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

            # Prefer full content over summary if available
            import re
            content = getattr(entry, "content", None)
            if content and isinstance(content, list) and content[0].get("value"):
                summary = content[0]["value"]
            summary = re.sub(r"<[^>]+>", "", summary)[:800]

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


def _fetch_all_feeds(max_workers: int = 6, slot: str | None = None) -> list[dict]:
    """Fetch feeds in parallel. If slot given, only fetch that slot's sources."""
    allowed = _SLOT_SOURCES.get(slot) if slot else None
    feeds = [(name, url) for name, url in _RSS_FEEDS if allowed is None or name in allowed]
    all_articles: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_feed, name, url): name for name, url in feeds}
        for future in as_completed(futures):
            all_articles.extend(future.result())
    return all_articles


@tool
def search_trending_ai_topics(query: str, max_results: int = 5, slot: str = "") -> str:
    """
    Search trending AI and tech news from RSS feeds — no API key required.

    Fetches from curated sources grouped by slot (morning=infra, afternoon=startup,
    evening=community, night=vietnam). Falls back to all sources if slot not given.

    Args:
        query:       Keywords to filter articles (English or Vietnamese).
        max_results: Number of articles to return (default 5).
        slot:        Optional slot name to filter sources (morning/afternoon/evening/night).

    Returns:
        Formatted string with title, source, URL, and summary per article.
    """
    max_results = max(1, min(max_results, 10))
    keywords = query.lower().split()

    logger.info("Fetching RSS feeds for query: %r  slot: %r", query, slot or "all")
    articles = _fetch_all_feeds(slot=slot or None)

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
