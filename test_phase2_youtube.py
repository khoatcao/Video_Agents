"""
Phase 2b test: post an existing MP4 to YouTube Shorts.

Requires in .env:
    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN

Usage:
    python test_phase2_youtube.py --mp4 outputs/morning_xxx.mp4
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("test_phase2_youtube")


def run(mp4_path: str) -> None:
    from tools.youtube_api import upload_youtube_short

    title = "AI Agent là gì? Giải thích trong 60 giây #Shorts"
    description = (
        "🤖 AI Agent là gì? Tìm hiểu ngay trong video này!\n\n"
        "Agent AI có khả năng:\n"
        "✅ Tự động tìm kiếm thông tin\n"
        "✅ Lên kế hoạch và thực thi\n"
        "✅ Học hỏi từ kết quả\n\n"
        "#AIAgent #CôngNghệAI #HọcAI #Shorts"
    )
    tags = ["AI Agent", "Công nghệ AI", "Học AI", "LangChain", "Vietnam Tech"]

    logger.info("Uploading Short to YouTube...")
    logger.info("MP4: %s", mp4_path)
    logger.info("Title: %s", title)

    try:
        video_url = upload_youtube_short(mp4_path, title, description, tags)
        logger.info("Short uploaded!")
        logger.info("URL: %s", video_url)
    except Exception as exc:
        logger.error("Upload failed: %s", exc)
        sys.exit(1)

    logger.info("=== YOUTUBE TEST COMPLETE ===")
    logger.info("Check your YouTube channel to verify the Short.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mp4", required=True, help="Path to MP4 file from Phase 1")
    args = parser.parse_args()
    run(args.mp4)
