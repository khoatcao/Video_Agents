"""
Affiliate Agent nodes for the LangGraph video-generation pipeline.

  affiliate_pre_node  — loads pre-generated Shopee affiliate links from
                        assets/affiliate_links.json and picks 3 randomly.
  affiliate_post_node — no-op; links are embedded in the Facebook caption.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

from state.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

_AFFILIATE_FILE = Path(__file__).resolve().parent.parent / "assets" / "affiliate_links.json"


def _load_affiliate_links() -> list[dict]:
    if not _AFFILIATE_FILE.is_file():
        logger.warning("[AffiliateAgent] %s not found.", _AFFILIATE_FILE)
        return []
    try:
        links = json.loads(_AFFILIATE_FILE.read_text(encoding="utf-8"))
        if isinstance(links, list):
            return links
    except Exception as exc:
        logger.warning("[AffiliateAgent] Failed to read affiliate_links.json: %s", exc)
    return []


def affiliate_pre_node(state: PipelineState) -> dict:
    links = _load_affiliate_links()
    if not links:
        logger.info("[AffiliateAgent/pre] No affiliate links in file.")
        return {"affiliate_links": []}

    picked = random.sample(links, min(3, len(links)))
    logger.info("[AffiliateAgent/pre] Picked %d affiliate links from file.", len(picked))
    return {"affiliate_links": picked}


def affiliate_post_node(state: PipelineState) -> dict:
    logger.info("[AffiliateAgent/post] Links embedded in caption — nothing to post.")
    return {"status": "completed"}
