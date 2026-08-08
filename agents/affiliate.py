"""
Affiliate Agent nodes for the LangGraph video-generation pipeline.

  affiliate_pre_node  — fetches Shopee products from Meta affiliate catalog.
                        Requires catalog_management permission (App Review).
                        Returns empty list until permission is approved.
  affiliate_post_node — no-op; links are embedded in the Facebook caption.
"""

from __future__ import annotations

import logging

from state.pipeline_state import PipelineState
from tools.facebook_api import get_affiliate_catalog_id, get_affiliate_products

logger = logging.getLogger(__name__)


def _meta_affiliate_products(topic: str, limit: int = 3) -> list[dict]:
    catalog_id = get_affiliate_catalog_id()
    if not catalog_id:
        return []

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


def affiliate_pre_node(state: PipelineState) -> dict:
    topic: str = state.get("topic", "")
    logger.info("[AffiliateAgent/pre] Fetching Shopee products from Meta affiliate catalog...")

    try:
        affiliate_links = _meta_affiliate_products(topic, limit=3)
    except Exception as exc:
        logger.warning("[AffiliateAgent/pre] Meta catalog failed: %s", exc)
        affiliate_links = []

    if not affiliate_links:
        logger.info("[AffiliateAgent/pre] No affiliate links — catalog requires App Review approval.")
        return {"affiliate_links": []}

    logger.info("[AffiliateAgent/pre] Got %d affiliate links.", len(affiliate_links))
    return {"affiliate_links": affiliate_links}


def affiliate_post_node(state: PipelineState) -> dict:
    logger.info("[AffiliateAgent/post] Links embedded in caption — nothing to post.")
    return {"status": "completed"}
