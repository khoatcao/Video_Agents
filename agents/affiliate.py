"""
Affiliate Agent nodes for the LangGraph video-generation pipeline.

Two nodes are exported:

  affiliate_pre_node  — runs BEFORE the Facebook/YouTube upload.
                        Fetches candidate products and uses deepseek-r1:7b to
                        rank/select the best 3 for the topic.

  affiliate_post_node — runs AFTER Facebook publishes the reel.
                        Formats the affiliate links into a comment and posts it.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config.prompts.affiliate_agent import AFFILIATE_AGENT_SYSTEM_PROMPT
from config.settings import MODEL_AFFILIATE, OLLAMA_BASE_URL
from state.pipeline_state import PipelineState
from tools.affiliate_api import (
    format_affiliate_comment,
    get_hot_products,
)
from tools.facebook_api import post_facebook_comment

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _strip_think_tags(text: str) -> str:
    """Remove <think>…</think> reasoning blocks emitted by deepseek-r1 models."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json_array(text: str) -> list[Any]:
    """
    Extract the first JSON array from *text*.

    Falls back to returning an empty list if no valid array is found.
    """
    text = _strip_think_tags(text)

    # Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Find first [ … ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            result = json.loads(text[start : end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    logger.warning("[AffiliateAgent] Could not extract JSON array from response; returning [].")
    return []


def _topic_to_keywords(topic: str) -> list[str]:
    """
    Derive 1–3 search keywords from the topic string.

    Splits on common delimiters and returns up to three meaningful tokens.
    """
    # Normalise and split
    parts = re.split(r"[\s\-/,]+", topic.strip())
    # Filter short tokens
    keywords = [p for p in parts if len(p) >= 3]
    if not keywords:
        keywords = [topic.strip()]
    # Return up to 3
    return keywords[:3]


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

    # ── 1. Fetch hot/trending products from AccessTrade ───────────────────────
    candidate_products: list[dict] = []
    try:
        candidate_products = get_hot_products(limit=10)
        logger.info("[AffiliateAgent/pre] Got %d hot products.", len(candidate_products))
    except Exception as exc:
        logger.warning("[AffiliateAgent/pre] AccessTrade hot products failed: %s", exc)

    if not candidate_products:
        logger.warning("[AffiliateAgent/pre] No hot products found; returning empty list.")
        return {"affiliate_links": []}

    # Take top 3 hottest products directly — no LLM selection needed
    top3 = candidate_products[:3]
    logger.info("[AffiliateAgent/pre] Using top %d hot products.", len(top3))
    return {"affiliate_links": top3}


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
    facebook_post_id: str = state.get("facebook_post_id", "")

    if not affiliate_links:
        logger.info("[AffiliateAgent/post] No affiliate links to post.")
        return {"status": "completed"}

    if not facebook_post_id:
        logger.warning("[AffiliateAgent/post] facebook_post_id is empty — cannot post comment.")
        return {"status": "completed"}

    # ── Format comment ─────────────────────────────────────────────────────────
    try:
        comment_text = format_affiliate_comment(affiliate_links)
    except Exception as exc:
        logger.error("[AffiliateAgent/post] format_affiliate_comment failed: %s", exc)
        return {"status": "completed"}  # Non-fatal: skip comment, pipeline is still done

    if not comment_text:
        logger.info("[AffiliateAgent/post] Formatted comment is empty; skipping post.")
        return {"status": "completed"}

    # ── Post comment to Facebook ───────────────────────────────────────────────
    logger.info(
        "[AffiliateAgent/post] Posting affiliate comment to post_id=%s", facebook_post_id
    )
    try:
        comment_id = post_facebook_comment(facebook_post_id, comment_text)
        logger.info("[AffiliateAgent/post] Comment posted. comment_id=%s", comment_id)
    except Exception as exc:
        logger.error("[AffiliateAgent/post] Failed to post comment: %s", exc)
        # Non-fatal — the video is already published; just log the failure.
        return {"status": "completed"}

    return {"status": "completed"}
