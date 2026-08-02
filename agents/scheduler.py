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

_SLOT_ORDER = ["morning", "afternoon", "evening"]

_FALLBACK_TOPICS = {
    "morning": "LangGraph multi-agent workflow",
    "afternoon": "RAG pipeline với Vietnamese corpus",
    "evening": "Local LLM với Ollama và deepseek-r1",
}


def _generate_daily_topics() -> dict[str, str]:
    """
    Call a fast LLM to generate 3 different AI/tech topics for today.

    Returns a dict: {"morning": "…", "afternoon": "…", "evening": "…"}.
    Falls back to _FALLBACK_TOPICS on any error.
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_ollama import ChatOllama

        from config.settings import MODEL_FAST, OLLAMA_BASE_URL

        llm = ChatOllama(
            model=MODEL_FAST,
            base_url=OLLAMA_BASE_URL,
            temperature=0.9,
            format="json",
        )
        today_str = date.today().strftime("%d/%m/%Y")
        messages = [
            SystemMessage(content=(
                "Bạn là người lên kế hoạch nội dung cho kênh AI/Tech tại Việt Nam. "
                "Trả về đúng một đối tượng JSON với ba key: "
                "\"morning\", \"afternoon\", \"evening\". "
                "Mỗi giá trị là một chủ đề video ngắn (tiếng Anh, 3–8 từ) phù hợp để "
                "giải thích cho lập trình viên Việt Nam. Ba chủ đề phải khác nhau. "
                "Chỉ trả về JSON."
            )),
            HumanMessage(content=f"Hôm nay {today_str}. Đề xuất 3 chủ đề video AI/Tech."),
        ]
        response = llm.invoke(messages)
        raw: str = response.content if hasattr(response, "content") else str(response)

        import re
        # Strip <think> tags
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        import json as _json
        data = _json.loads(raw)
        if all(k in data and isinstance(data[k], str) for k in _SLOT_ORDER):
            logger.info("[Scheduler] Generated daily topics: %s", data)
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


# ── Pipeline runner ────────────────────────────────────────────────────────────

def run_pipeline(slot: str) -> None:
    """
    Fetch today's topic for *slot* and run the full LangGraph pipeline.

    Logs success/failure to logs/pipeline.log.
    """
    from graph.pipeline import run_pipeline_graph  # lazy import to avoid circular deps

    topic = get_topic_for_slot(slot)
    start_ts = datetime.now(tz=pytz.timezone(TIMEZONE))
    logger.info(
        "[Scheduler] *** Starting pipeline: slot=%s  topic=%r  time=%s ***",
        slot,
        topic,
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
                "[Scheduler] Pipeline COMPLETED. YouTube=%s  Facebook=%s",
                youtube_url or "(none)",
                facebook_url or "(none)",
            )
        else:
            logger.error(
                "[Scheduler] Pipeline ended with status=%r  error=%s",
                status,
                error,
            )
    except Exception as exc:
        logger.exception(
            "[Scheduler] Unhandled exception running pipeline for slot=%s: %s",
            slot,
            exc,
        )

    end_ts = datetime.now(tz=pytz.timezone(TIMEZONE))
    duration = (end_ts - start_ts).total_seconds()
    logger.info(
        "[Scheduler] Pipeline for slot=%s finished in %.1fs.",
        slot,
        duration,
    )


# ── Main entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Video-Agent scheduler — run now or start cron jobs."
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run the pipeline immediately and exit (use with --slot).",
    )
    parser.add_argument(
        "--slot",
        choices=["morning", "afternoon", "evening"],
        default="morning",
        help="Which slot to run (only used with --run-now).",
    )
    args = parser.parse_args()

    if args.run_now:
        logger.info("[Scheduler] --run-now mode: slot=%s", args.slot)
        run_pipeline(args.slot)
        return

    # ── Start persistent APScheduler ──────────────────────────────────────────
    tz = pytz.timezone(TIMEZONE)
    scheduler = BlockingScheduler(timezone=tz)

    scheduler.add_job(
        func=run_pipeline,
        trigger=CronTrigger(hour=8, minute=0, timezone=tz),
        args=["morning"],
        id="morning_pipeline",
        name="Morning AI video (08:00 ICT)",
        replace_existing=True,
    )
    scheduler.add_job(
        func=run_pipeline,
        trigger=CronTrigger(hour=12, minute=30, timezone=tz),
        args=["afternoon"],
        id="afternoon_pipeline",
        name="Afternoon AI video (12:30 ICT)",
        replace_existing=True,
    )
    scheduler.add_job(
        func=run_pipeline,
        trigger=CronTrigger(hour=20, minute=0, timezone=tz),
        args=["evening"],
        id="evening_pipeline",
        name="Evening AI video (20:00 ICT)",
        replace_existing=True,
    )

    logger.info(
        "[Scheduler] Starting scheduler. Jobs: 08:00, 12:30, 20:00 %s. Press Ctrl+C to stop.",
        TIMEZONE,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("[Scheduler] Scheduler stopped.")


if __name__ == "__main__":
    main()
