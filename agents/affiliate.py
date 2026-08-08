"""
Affiliate Agent — loads Shopee affiliate URLs from assets/affiliate_links.json.
Picks 3 random links per run and embeds them in the Facebook caption.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

from state.pipeline_state import PipelineState

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
    # Convert to simple dicts for state compatibility
    links = [{"product_name": "", "url": u, "platform": "shopee", "price_range": ""} for u in picked]
    logger.info("[AffiliateAgent/pre] Picked %d affiliate links.", len(links))
    return {"affiliate_links": links}


def affiliate_post_node(state: PipelineState) -> dict:
    logger.info("[AffiliateAgent/post] Links embedded in caption — nothing to post.")
    return {"status": "completed"}
