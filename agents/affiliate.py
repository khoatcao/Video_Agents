"""
Affiliate Agent nodes for the LangGraph video-generation pipeline.

  affiliate_pre_node  — fetches top campaigns from AccessTrade, generates
                        affiliate tracking links, stores in state.
  affiliate_post_node — posts affiliate links as first comment on Facebook Reel.
"""

from __future__ import annotations

import logging
import time

from state.pipeline_state import PipelineState
from tools.affiliate_api import (
    format_affiliate_comment,
    get_hot_products,
)
from tools.facebook_api import post_facebook_comment

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

    if not comment_target:
        logger.warning("[AffiliateAgent/post] No facebook video_id — cannot post comment.")
        return {"status": "completed"}

    # ── Format comment ─────────────────────────────────────────────────────────
    try:
        comment_text = format_affiliate_comment(affiliate_links)
    except Exception as exc:
        logger.error("[AffiliateAgent/post] format_affiliate_comment failed: %s", exc)
        return {"status": "completed"}

    if not comment_text:
        logger.info("[AffiliateAgent/post] Formatted comment is empty; skipping post.")
        return {"status": "completed"}

    # ── Post comment (retry — video needs time to finish processing) ───────────
    logger.info("[AffiliateAgent/post] Posting comment to video_id=%s", comment_target)
    _MAX_ATTEMPTS = 3
    _WAIT_SECONDS = 20

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            comment_id = post_facebook_comment(comment_target, comment_text)
            logger.info("[AffiliateAgent/post] Comment posted. comment_id=%s", comment_id)
            return {"status": "completed"}
        except Exception as exc:
            logger.warning(
                "[AffiliateAgent/post] Attempt %d/%d failed: %s",
                attempt, _MAX_ATTEMPTS, exc,
            )
            if attempt < _MAX_ATTEMPTS:
                logger.info(
                    "[AffiliateAgent/post] Waiting %ds before retry…", _WAIT_SECONDS,
                )
                time.sleep(_WAIT_SECONDS)

    logger.error(
        "[AffiliateAgent/post] All %d attempts failed — comment NOT posted. video_id=%s",
        _MAX_ATTEMPTS, comment_target,
    )
    return {"status": "completed"}
