"""
Scheduler for the video-generation pipeline.

Runs three daily pipeline jobs (UTC+7 / Asia/Ho_Chi_Minh):
  - morning   → 08:00
  - afternoon → 12:30
  - evening   → 20:00

Usage:
  # Start the persistent scheduler (blocks):
  python -m agents.scheduler

  # Run a single slot immediately and exit:
  python -m agents.scheduler --run-now --slot morning
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import TIMEZONE

# ── Logging setup ──────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOGS_DIR = _PROJECT_ROOT / "logs"
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

_LOG_FILE = _LOGS_DIR / "pipeline.log"
_TOPICS_FILE = _LOGS_DIR / "daily_topics.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(_LOG_FILE), encoding="utf-8"),
    ],
)
logger = logging.getLogger("scheduler")

# ── Slot → topic mapping helpers ──────────────────────────────────────────────

_SLOT_ORDER = ["morning", "afternoon", "evening", "night"]

_FALLBACK_TOPICS = {
    "morning":   "NVIDIA Blackwell GPU AI training",
    "afternoon": "AI startup funding trends 2025",
    "evening":   "Open source LLM tools for developers",
    "night":     "Trí tuệ nhân tạo tại Việt Nam 2025",
}


_AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "gemini", "machine learning", "deep learning",
    "neural", "agent", "chatbot", "openai", "anthropic", "model", "transformer",
    "diffusion", "generative", "automation", "robot", "nlp", "computer vision",
    "trí tuệ nhân tạo", "học máy", "mô hình", "tự động hóa",
]


def _fetch_trending_headlines(max_per_source: int = 2, max_total: int = 20) -> str:
    """
    Fetch AI-related headlines from RSS feeds, diverse across sources.

    Strategy:
    1. Filter articles to AI/tech relevant ones using keyword scoring.
    2. Take top `max_per_source` per source to ensure diversity.
    3. Sort final list by recency.
    """
    try:
        from tools.web_search import _fetch_all_feeds

        articles = _fetch_all_feeds()
        if not articles:
            return ""

        # Score each article by AI keyword matches
        def ai_score(article: dict) -> int:
            text = (article["title"] + " " + article.get("summary", "")).lower()
            return sum(1 for kw in _AI_KEYWORDS if kw in text)

        # Keep only articles with at least 1 AI keyword match
        relevant = [a for a in articles if ai_score(a) > 0]

        # If not enough AI articles, fall back to all articles
        if len(relevant) < 5:
            relevant = articles

        # Take top max_per_source from each source (by recency)
        by_source: dict[str, list] = {}
        for a in sorted(relevant, key=lambda x: x["published"], reverse=True):
            src = a["source"]
            by_source.setdefault(src, [])
            if len(by_source[src]) < max_per_source:
                by_source[src].append(a)

        # Flatten, sort by recency, cap at max_total
        diverse = [a for src_articles in by_source.values() for a in src_articles]
        diverse.sort(key=lambda a: a["published"], reverse=True)
        top = diverse[:max_total]

        lines = [f"- {a['title']} ({a['source']})" for a in top]
        logger.info("[Scheduler] Selected %d AI headlines from %d sources.", len(top), len(by_source))
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("[Scheduler] RSS fetch for topic planning failed: %s", exc)
        return ""


def _generate_daily_topics() -> dict[str, str]:
    """
    Fetch trending RSS headlines then ask LLM to pick 3 topic ideas from real news.

    Returns a dict: {"morning": "…", "afternoon": "…", "evening": "…"}.
    Falls back to _FALLBACK_TOPICS on any error.
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_ollama import ChatOllama

        from config.settings import MODEL_FAST, OLLAMA_BASE_URL

        headlines = _fetch_trending_headlines()
        today_str = date.today().strftime("%d/%m/%Y")

        if headlines:
            news_block = f"Tin tức AI/Tech mới nhất hôm nay ({today_str}):\n{headlines}\n\n"
            instruction = (
                "Dựa vào các tin tức trên, chọn 3 chủ đề video khác nhau phù hợp nhất "
                "để giải thích cho lập trình viên Việt Nam. Ưu tiên chủ đề đang trending."
            )
        else:
            news_block = ""
            instruction = f"Hôm nay {today_str}. Đề xuất 3 chủ đề video AI/Tech đang trending."

        llm = ChatOllama(
            model=MODEL_FAST,
            base_url=OLLAMA_BASE_URL,
            temperature=0.9,
            format="json",
        )
        messages = [
            SystemMessage(content=(
                "Bạn là người lên kế hoạch nội dung cho kênh AI/Tech tại Việt Nam. "
                "Trả về đúng một đối tượng JSON với bốn key: "
                "\"morning\", \"afternoon\", \"evening\", \"night\". "
                "Quy tắc chọn topic theo slot:\n"
                "- morning: AI infra, GPU, model mới từ NVIDIA/Google/AWS/HuggingFace\n"
                "- afternoon: AI startup, product launch, business news\n"
                "- evening: open source tools, developer community, research\n"
                "- night: AI news liên quan đến Việt Nam, tiếng Việt\n"
                "Bốn chủ đề phải hoàn toàn khác nhau. Mỗi chủ đề 3–8 từ tiếng Anh. Chỉ trả về JSON."
            )),
            HumanMessage(content=news_block + instruction),
        ]
        response = llm.invoke(messages)
        raw: str = response.content if hasattr(response, "content") else str(response)

        import re
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        import json as _json
        data = _json.loads(raw)
        if all(k in data and isinstance(data[k], str) for k in _SLOT_ORDER):
            logger.info("[Scheduler] Generated daily topics from live news: %s", data)
            return {s: data[s] for s in _SLOT_ORDER}
    except Exception as exc:
        logger.warning("[Scheduler] Topic generation failed: %s — using fallbacks.", exc)

    return dict(_FALLBACK_TOPICS)


def get_topic_for_slot(slot: str) -> str:
    """
    Return today's pre-planned topic for *slot*.

    Checks logs/daily_topics.json for a matching entry dated today.
    If missing or stale, generates 3 topics for the day and saves them.
    """
    today_key = date.today().isoformat()  # e.g. "2024-12-01"

    # Load existing file
    existing: dict = {}
    if _TOPICS_FILE.is_file():
        try:
            existing = json.loads(_TOPICS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("[Scheduler] Failed to read daily_topics.json: %s", exc)

    # Check if today's topics are already generated
    if existing.get("date") == today_key and all(
        s in existing.get("topics", {}) for s in _SLOT_ORDER
    ):
        topic = existing["topics"].get(slot, _FALLBACK_TOPICS[slot])
        logger.info("[Scheduler] Using pre-planned topic for %s: %r", slot, topic)
        return topic

    # Generate new topics for today
    logger.info("[Scheduler] Generating new daily topics for %s …", today_key)
    topics = _generate_daily_topics()

    # Save to file
    payload = {"date": today_key, "topics": topics}
    try:
        _TOPICS_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("[Scheduler] Saved daily_topics.json for %s.", today_key)
    except OSError as exc:
        logger.warning("[Scheduler] Could not save daily_topics.json: %s", exc)

    return topics.get(slot, _FALLBACK_TOPICS[slot])


# Source groups — each maps to a specific set of RSS feeds
_SOURCE_GROUPS = ["infra", "startup", "community", "vietnam"]

# group → slot name used internally (for file naming + state)
_GROUP_TO_SLOT = {
    "infra":     "morning",
    "startup":   "afternoon",
    "community": "evening",
    "vietnam":   "night",
}


# ── Pipeline runner ────────────────────────────────────────────────────────────

def run_pipeline(group: str) -> None:
    """Run the full pipeline for one source group, generating 1 video."""
    from graph.pipeline import run_pipeline_graph

    slot = _GROUP_TO_SLOT.get(group, group)
    topic = get_topic_for_slot(slot)
    start_ts = datetime.now(tz=pytz.timezone(TIMEZONE))
    logger.info(
        "[Scheduler] *** Starting pipeline: group=%s  slot=%s  topic=%r  time=%s ***",
        group, slot, topic,
        start_ts.strftime("%Y-%m-%d %H:%M:%S %Z"),
    )

    try:
        final_state = run_pipeline_graph(topic=topic, slot=slot)
        status = final_state.get("status", "unknown")
        youtube_url = final_state.get("youtube_url", "")
        facebook_url = final_state.get("facebook_url", "")
        error = final_state.get("error")

        if status == "completed":
            logger.info(
                "[Scheduler] [%s] COMPLETED. YouTube=%s  Facebook=%s",
                group, youtube_url or "(none)", facebook_url or "(none)",
            )
        else:
            logger.error("[Scheduler] [%s] ended with status=%r  error=%s", group, status, error)
    except Exception as exc:
        logger.exception("[Scheduler] Unhandled exception for group=%s: %s", group, exc)

    duration = (datetime.now(tz=pytz.timezone(TIMEZONE)) - start_ts).total_seconds()
    logger.info("[Scheduler] [%s] finished in %.1fs.", group, duration)


def run_all_groups() -> None:
    """Run all 4 source groups sequentially → 4 videos per trigger."""
    logger.info("[Scheduler] === Running all 4 source groups ===")
    for group in _SOURCE_GROUPS:
        run_pipeline(group)
    logger.info("[Scheduler] === All 4 groups done ===")


# ── Main entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Video-Agent scheduler — generates 4 videos per run from 4 source groups."
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run all 4 source groups immediately and exit.",
    )
    parser.add_argument(
        "--group",
        choices=_SOURCE_GROUPS,
        default=None,
        help="Run only one specific source group (use with --run-now for testing).",
    )
    args = parser.parse_args()

    if args.run_now:
        if args.group:
            logger.info("[Scheduler] --run-now mode: single group=%s", args.group)
            run_pipeline(args.group)
        else:
            logger.info("[Scheduler] --run-now mode: all 4 groups")
            run_all_groups()
        return

    # ── Start persistent APScheduler — 3x daily, each run = 4 videos ─────────
    tz = pytz.timezone(TIMEZONE)
    scheduler = BlockingScheduler(timezone=tz)

    scheduler.add_job(
        func=run_all_groups,
        trigger=CronTrigger(hour=8, minute=0, timezone=tz),
        id="morning_batch",
        name="Morning batch — 4 videos (08:00 ICT)",
        replace_existing=True,
    )
    scheduler.add_job(
        func=run_all_groups,
        trigger=CronTrigger(hour=14, minute=0, timezone=tz),
        id="afternoon_batch",
        name="Afternoon batch — 4 videos (14:00 ICT)",
        replace_existing=True,
    )
    scheduler.add_job(
        func=run_all_groups,
        trigger=CronTrigger(hour=20, minute=0, timezone=tz),
        id="evening_batch",
        name="Evening batch — 4 videos (20:00 ICT)",
        replace_existing=True,
    )

    logger.info(
        "[Scheduler] Starting scheduler. Batches: 08:00, 14:00, 20:00 %s "
        "(4 videos per batch = 12 videos/day). Press Ctrl+C to stop.",
        TIMEZONE,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("[Scheduler] Scheduler stopped.")


if __name__ == "__main__":
    main()
