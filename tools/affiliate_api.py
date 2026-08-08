"""
Affiliate link helpers — AccessTrade Vietnam.

AccessTrade is Vietnam's largest affiliate network covering Shopee, Lazada,
Tiki, and hundreds of other merchants under one API.

API docs: https://accesstrade.vn/developer
Auth: Authorization: Token YOUR_API_KEY
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

import requests

from config.settings import ACCESSTRADE_API_KEY

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.accesstrade.vn/v1"
_REQUEST_TIMEOUT = 15

_HEADERS = {
    "Authorization": f"Token {ACCESSTRADE_API_KEY}",
    "Content-Type": "application/json",
}


# ── Hot/trending products ──────────────────────────────────────────────────────

def get_hot_products(limit: int = 10) -> list[dict[str, str]]:
    """
    Fetch currently hot/trending products from AccessTrade — no keyword needed.

    Sorted by click count (most clicked = most people are looking for).
    Returns list of product dicts: product_name, url, platform, price_range.
    """
    if not ACCESSTRADE_API_KEY:
        logger.warning("[AffiliateAPI] ACCESSTRADE_API_KEY not set — skipping.")
        return []

    limit = min(limit, 20)
    try:
        resp = requests.get(
            f"{_BASE_URL}/offers",
            headers=_HEADERS,
            params={
                "page_size": limit,
                "order_by": "-click_count",  # descending = hottest first
            },
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []
    except Exception as exc:
        logger.warning("[AffiliateAPI] AccessTrade hot products failed: %s", exc)
        return []

    results: list[dict[str, str]] = []
    for item in items[:limit]:
        name: str = item.get("name") or item.get("product_name") or item.get("offer_name", "")
        url: str = item.get("url") or item.get("product_url") or item.get("offer_url", "")
        price = item.get("price") or item.get("min_price") or 0
        merchant: str = item.get("merchant_name") or item.get("campaign_name", "")

        if not name or not url:
            continue

        affiliate_url = generate_affiliate_link(url) or url
        price_str = f"{int(price):,} VND".replace(",", ".") if price else "Xem trên AccessTrade"
        results.append({
            "product_name": name,
            "url": affiliate_url,
            "platform": merchant.lower() if merchant else "accesstrade",
            "price_range": price_str,
        })

    logger.info("[AffiliateAPI] Got %d hot products from AccessTrade.", len(results))
    return results


def generate_affiliate_link(product_url: str) -> str:
    """
    Convert any product URL (Shopee, Lazada, Tiki, etc.) to an AccessTrade affiliate link.

    Returns the affiliate link on success, empty string on failure.
    """
    if not ACCESSTRADE_API_KEY:
        return ""

    try:
        resp = requests.post(
            f"{_BASE_URL}/link_generate",
            headers=_HEADERS,
            json={"url": product_url},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        link = data.get("data") or data.get("link") or data.get("affiliate_url", "")
        return str(link) if link else ""
    except Exception as exc:
        logger.warning("[AffiliateAPI] Link generation failed for %r: %s", product_url, exc)
        return ""


# ── Comment formatter ──────────────────────────────────────────────────────────

def format_affiliate_comment(products: list[dict[str, str]]) -> str:
    """
    Render a Vietnamese comment string listing affiliate products.

    Posted as the first comment on a Facebook Reel.
    """
    if not products:
        return ""

    lines: list[str] = [
        "🛒 Sản phẩm liên quan trong video:",
        "",
    ]
    for product in products:
        name = product.get("product_name", "Sản phẩm")
        url = product.get("url", "")
        price = product.get("price_range", "")
        price_str = f" — {price}" if price and "Xem" not in price else ""
        lines.append(f"🔗 {name}{price_str}")
        if url:
            lines.append(f"   👉 {url}")
        lines.append("")

    lines.append("💡 Giá có thể thay đổi. Kiểm tra trước khi mua nhé!")
    return "\n".join(lines)
