"""
Phase 2a test: post an existing MP4 to Facebook Reels.

Requires in .env:
    FACEBOOK_ACCESS_TOKEN
    FACEBOOK_PAGE_ID

Usage:
    python test_phase2_facebook.py --mp4 outputs/morning_xxx.mp4
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("test_phase2_facebook")


def run(mp4_path: str) -> None:
    from tools.facebook_api import post_facebook_comment, upload_facebook_reel

    test_caption = (
        "🤖 AI Agent là gì? Tìm hiểu ngay!\n"
        "#AIAgent #CôngNghệAI #HọcAI\n\n"
        "🛒 Khoá học AI được recommend:\n"
        "👉 https://shopee.vn"
    )

    logger.info("Uploading Reel to Facebook...")
    logger.info("MP4: %s", mp4_path)

    try:
        post_id = upload_facebook_reel(mp4_path, test_caption)
        logger.info("Reel uploaded! Post ID: %s", post_id)
    except Exception as exc:
        logger.error("Upload failed: %s", exc)
        sys.exit(1)

    logger.info("Posting affiliate comment...")
    test_comment = (
        "📚 Tài nguyên học AI mình recommend:\n"
        "1. Khoá học Python AI - https://shopee.vn\n"
        "2. Sách AI cơ bản - https://tiki.vn\n"
        "\n💡 Giá có thể thay đổi. Kiểm tra trước khi mua nhé!"
    )

    try:
        comment_id = post_facebook_comment(post_id, test_comment)
        logger.info("Comment posted! Comment ID: %s", comment_id)
    except Exception as exc:
        logger.error("Comment failed: %s", exc)
        sys.exit(1)

    logger.info("=== FACEBOOK TEST COMPLETE ===")
    logger.info("Check your Facebook Page to verify the Reel and comment.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mp4", required=True, help="Path to MP4 file from Phase 1")
    args = parser.parse_args()
    run(args.mp4)
