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

def get_hot_products(limit: int = 3) -> list[dict[str, str]]:
    """
    Fetch joined campaigns from AccessTrade and generate affiliate links for each.

    Strategy: get active campaigns → generate tracking link → return as product list.
    """
    if not ACCESSTRADE_API_KEY:
        logger.warning("[AffiliateAPI] ACCESSTRADE_API_KEY not set — skipping.")
        return []

    # Step 1: Get approved joined campaigns (relationship=1 = approved by merchant)
    try:
        resp = requests.get(
            f"{_BASE_URL}/campaigns",
            headers=_headers(),
            params={"relationship": 1, "page": 1, "limit": 20},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("[AffiliateAPI] campaigns response: %s", str(data)[:300])
        campaigns = data.get("data", [])
        if not isinstance(campaigns, list):
            campaigns = []
    except Exception as exc:
        logger.warning("[AffiliateAPI] AccessTrade campaigns failed: %s", exc)
        return []

    if not campaigns:
        logger.warning("[AffiliateAPI] No active campaigns found.")
        return []

    def _format_commission(val) -> str:
        """Format max_com: ≤100 → percentage, >100 → VND fixed amount."""
        raw = str(val).replace("%", "").split("/")[0].strip()
        try:
            num = float(raw)
        except (ValueError, TypeError):
            return ""
        if "%" in str(val) or num <= 100:
            return f"Hoa hồng {num:.0f}%"
        return f"Hoa hồng {int(num):,}đ".replace(",", ".")

    # Step 2: Pick top campaigns by commission rate
    def _parse_commission(val) -> float:
        try:
            # Strip %, take first number before "/" (e.g. "4/9%" → 4.0, "14%" → 14.0)
            return float(str(val).replace("%", "").split("/")[0].strip())
        except (ValueError, TypeError):
            return 0.0

    campaigns.sort(key=lambda c: _parse_commission(c.get("max_com", 0)), reverse=True)
    top_campaigns = campaigns[:limit]

    # Step 3: Generate affiliate link for each campaign
    results: list[dict[str, str]] = []
    for campaign in top_campaigns:
        name: str = campaign.get("name", "")
        url: str = campaign.get("url", "")
        campaign_id: str = str(campaign.get("id", ""))
        max_com: str = campaign.get("max_com", "")

        if not name or not url:
            continue

        aff_link = generate_affiliate_link(url, campaign_id=campaign_id)
        if not aff_link:
            logger.warning("[AffiliateAPI] generate_affiliate_link failed for %s — skipping.", name)
            continue

        commission = _format_commission(max_com)

        results.append({
            "product_name": name,
            "url": aff_link,
            "platform": campaign.get("merchant", "accesstrade"),
            "price_range": commission,
        })

    logger.info("[AffiliateAPI] Got %d campaign affiliate links.", len(results))
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
        logger.info("[AffiliateAPI] product_link/create response: %s", str(data)[:300])
        success_links = data.get("data", {}).get("success_link", [])
        if success_links:
            return success_links[0].get("aff_link") or success_links[0].get("short_link", "")
        fail_links = data.get("data", {}).get("fail_link", [])
        if fail_links:
            logger.warning("[AffiliateAPI] Link rejected by AccessTrade: %s", fail_links)
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
