"""
Affiliate Agent nodes for the LangGraph video-generation pipeline.

  affiliate_pre_node  — fetches Shopee products from Meta affiliate catalog
                        (falls back to AccessTrade if catalog unavailable).
  affiliate_post_node — no-op; links are embedded in the Facebook caption.
"""

from __future__ import annotations

import logging

from state.pipeline_state import PipelineState
from tools.affiliate_api import get_hot_products
from tools.facebook_api import get_affiliate_catalog_id, get_affiliate_products

logger = logging.getLogger(__name__)


def _meta_affiliate_products(topic: str, limit: int = 3) -> list[dict]:
    """
    Fetch Shopee products from Meta affiliate catalog linked to the Page.
    Returns list of AffiliateLink-compatible dicts, empty on failure.
    """
    catalog_id = get_affiliate_catalog_id()
    if not catalog_id:
        logger.warning("[AffiliateAgent] No Meta affiliate catalog found on Page.")
        return []

    # Use topic keywords as search query
    keyword = topic.split()[0] if topic else ""
    products = get_affiliate_products(catalog_id, query=keyword, limit=limit)

    results: list[dict] = []
    for p in products:
        name = p.get("name", "")
        url = p.get("url", "")
        if not name or not url:
            continue
        price = p.get("sale_price") or p.get("price", "")
        results.append({
            "product_name": name,
            "url": url,
            "platform": "shopee",
            "price_range": str(price),
            "meta_product_id": p.get("id", ""),
        })

    logger.info("[AffiliateAgent] Got %d products from Meta affiliate catalog.", len(results))
    return results


# ── Node 1: Pre-upload affiliate product selection ─────────────────────────────

def affiliate_pre_node(state: PipelineState) -> dict:
    topic: str = state.get("topic", "")

    # Strategy 1: Meta native affiliate catalog (Shopee linked to Page)
    logger.info("[AffiliateAgent/pre] Trying Meta affiliate catalog...")
    try:
        affiliate_links = _meta_affiliate_products(topic, limit=3)
    except Exception as exc:
        logger.warning("[AffiliateAgent/pre] Meta catalog failed: %s", exc)
        affiliate_links = []

    # Strategy 2: AccessTrade fallback
    if not affiliate_links:
        logger.info("[AffiliateAgent/pre] Falling back to AccessTrade...")
        try:
            affiliate_links = get_hot_products(limit=3)
        except Exception as exc:
            logger.warning("[AffiliateAgent/pre] AccessTrade failed: %s", exc)

    if not affiliate_links:
        logger.warning("[AffiliateAgent/pre] No affiliate links found.")
        return {"affiliate_links": []}

    logger.info("[AffiliateAgent/pre] Using %d affiliate links.", len(affiliate_links))
    return {"affiliate_links": affiliate_links}


# ── Node 2: Post-upload (no-op — links are in caption) ────────────────────────

def affiliate_post_node(state: PipelineState) -> dict:
    logger.info("[AffiliateAgent/post] Links embedded in caption — nothing to post.")
    return {"status": "completed"}
