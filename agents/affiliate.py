"""
Affiliate Agent nodes for the LangGraph video-generation pipeline.

  affiliate_pre_node  — fetches top campaigns from AccessTrade, generates
                        affiliate tracking links, stores in state.
  affiliate_post_node — posts affiliate links as first comment on Facebook Reel.
"""

from __future__ import annotations

import logging

from state.pipeline_state import PipelineState
from tools.affiliate_api import get_hot_products

logger = logging.getLogger(__name__)



# ── Node 1: Pre-upload affiliate product selection ─────────────────────────────

def affiliate_pre_node(state: PipelineState) -> dict:
    """
    LangGraph node (runs before upload): fetch + rank affiliate products.

    Reads:
        state["topic"], state["scene_plan"]

    Writes:
        affiliate_links  — list of up to 3 AffiliateLink dicts
        — or —
        error (non-fatal; pipeline continues with empty affiliate_links)
    """
    topic: str = state.get("topic", "")
    scene_plan = state.get("scene_plan", [])

    logger.info("[AffiliateAgent/pre] Fetching hot products from AccessTrade...")

    # ── 1. Fetch top campaign affiliate links from AccessTrade ────────────────
    affiliate_links: list[dict] = []
    try:
        affiliate_links = get_hot_products(limit=3)
        logger.info("[AffiliateAgent/pre] Got %d campaign links.", len(affiliate_links))
    except Exception as exc:
        logger.warning("[AffiliateAgent/pre] AccessTrade campaigns failed: %s", exc)

    if not affiliate_links:
        logger.warning("[AffiliateAgent/pre] No campaign links found; returning empty list.")
        return {"affiliate_links": []}

    return {"affiliate_links": affiliate_links}


# ── Node 2: Post-upload comment with affiliate links ──────────────────────────

def affiliate_post_node(state: PipelineState) -> dict:
    """
    LangGraph node (runs after Facebook upload): post affiliate links as a comment.

    Reads:
        state["affiliate_links"], state["facebook_post_id"]

    Writes:
        status="completed"  — on success
        — or —
        error               — on failure (non-fatal; pipeline still finishes)
    """
    affiliate_links = state.get("affiliate_links", [])
    # Use video_id for comments — post_id uses the deprecated singular statuses API (error #12)
    comment_target: str = state.get("facebook_video_id", "") or state.get("facebook_post_id", "")

    if not affiliate_links:
        logger.info("[AffiliateAgent/post] No affiliate links to post.")
        return {"status": "completed"}

    # Affiliate links are embedded in the caption by facebook_node.
    # Comment posting requires pages_manage_engagement (needs Facebook App Review).
    # Skip for now — links are already visible in the caption.
    logger.info(
        "[AffiliateAgent/post] Affiliate links already in caption. "
        "Comment posting skipped (needs pages_manage_engagement App Review)."
    )
    return {"status": "completed"}
