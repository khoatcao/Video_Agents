"""
Affiliate Agent — loads Shopee affiliate URLs from assets/affiliate_links.json.
Picks 3 random links, tries to post as comment after upload.
Falls back to caption if pages_manage_engagement not yet approved.
"""

from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path

from state.pipeline_state import PipelineState
from tools.facebook_api import post_facebook_comment

logger = logging.getLogger(__name__)

_AFFILIATE_FILE = Path(__file__).resolve().parent.parent / "assets" / "affiliate_links.json"


def _load_urls() -> list[str]:
    if not _AFFILIATE_FILE.is_file():
        logger.warning("[AffiliateAgent] affiliate_links.json not found.")
        return []
    try:
        data = json.loads(_AFFILIATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(u) for u in data if u]
    except Exception as exc:
        logger.warning("[AffiliateAgent] Failed to read affiliate_links.json: %s", exc)
    return []


def affiliate_pre_node(state: PipelineState) -> dict:
    urls = _load_urls()
    if not urls:
        logger.info("[AffiliateAgent/pre] No affiliate URLs found.")
        return {"affiliate_links": []}

    picked = random.sample(urls, min(3, len(urls)))
    links = [{"product_name": "", "url": u, "platform": "shopee", "price_range": ""} for u in picked]
    logger.info("[AffiliateAgent/pre] Picked %d affiliate links.", len(links))
    return {"affiliate_links": links}


def affiliate_post_node(state: PipelineState) -> dict:
    affiliate_links = state.get("affiliate_links", [])
    video_id: str = state.get("facebook_video_id", "")

    if not affiliate_links or not video_id:
        logger.info("[AffiliateAgent/post] Nothing to post.")
        return {"status": "completed"}

    urls = [p.get("url", "") for p in affiliate_links if p.get("url")]
    if not urls:
        return {"status": "completed"}

    comment_text = "🛒 Link sản phẩm:\n" + "\n".join(f"👉 {u}" for u in urls)

    # Wait for Facebook to finish processing the reel before commenting
    logger.info("[AffiliateAgent/post] Waiting 30s for reel to process...")
    time.sleep(30)

    logger.info("[AffiliateAgent/post] Posting affiliate comment to video_id=%s", video_id)
    try:
        comment_id = post_facebook_comment(video_id, comment_text)
        logger.info("[AffiliateAgent/post] Comment posted. comment_id=%s", comment_id)
        # Comment succeeded — remove links from caption next run (state already set)
        return {"status": "completed"}
    except Exception as exc:
        logger.warning(
            "[AffiliateAgent/post] Comment failed (%s) — links already in caption as fallback.", exc
        )
        return {"status": "completed"}
