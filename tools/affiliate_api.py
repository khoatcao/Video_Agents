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

def _headers() -> dict:
    return {
        "Authorization": f"Token {ACCESSTRADE_API_KEY}",
        "Content-Type": "application/json",
    }


# ── Hot/trending products ──────────────────────────────────────────────────────

def get_hot_products(limit: int = 10) -> list[dict[str, str]]:
    """
    Fetch top best-selling products from AccessTrade — no keyword needed.

    Uses /v1/top_products endpoint, returns products with ready-made aff_link.
    """
    if not ACCESSTRADE_API_KEY:
        logger.warning("[AffiliateAPI] ACCESSTRADE_API_KEY not set — skipping.")
        return []

    from datetime import datetime, timedelta
    date_to = datetime.now().strftime("%d-%m-%Y")
    date_from = (datetime.now() - timedelta(days=7)).strftime("%d-%m-%Y")

    try:
        resp = requests.get(
            f"{_BASE_URL}/top_products",
            headers=_headers(),
            params={"date_from": date_from, "date_to": date_to},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("[AffiliateAPI] top_products raw response: %s", str(data)[:500])
        items = data.get("data", [])
        if not isinstance(items, list):
            items = []
    except Exception as exc:
        logger.warning("[AffiliateAPI] AccessTrade top_products failed: %s", exc)
        return []

    results: list[dict[str, str]] = []
    for item in items[:limit]:
        name: str = item.get("name", "")
        aff_link: str = item.get("aff_link") or item.get("link", "")
        price = item.get("price") or 0
        category: str = item.get("category_name", "")

        if not name or not aff_link:
            continue

        price_str = f"{int(float(price)):,} VND".replace(",", ".") if price else "Xem trên AccessTrade"
        results.append({
            "product_name": name,
            "url": aff_link,
            "platform": category.lower() if category else "accesstrade",
            "price_range": price_str,
        })

    logger.info("[AffiliateAPI] Got %d hot products from AccessTrade.", len(results))
    return results


def generate_affiliate_link(product_url: str, campaign_id: str = "") -> str:
    """
    Convert any product URL to an AccessTrade affiliate tracking link.

    Endpoint: POST /v1/product_link/create
    Returns the aff_link on success, empty string on failure.
    """
    if not ACCESSTRADE_API_KEY:
        return ""

    try:
        payload: dict = {"urls": product_url}
        if campaign_id:
            payload["campaign_id"] = campaign_id

        resp = requests.post(
            f"{_BASE_URL}/product_link/create",
            headers=_headers(),
            json=payload,
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        success_links = data.get("data", {}).get("success_link", [])
        if success_links:
            return success_links[0].get("aff_link") or success_links[0].get("short_link", "")
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
