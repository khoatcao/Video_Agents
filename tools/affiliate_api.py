"""
Affiliate link helpers for the Vietnamese market.

Supported networks:
  - Shopee Vietnam  (unofficial product search + affiliate deep-link)
  - Lazada Vietnam  (affiliate deep-link via tracking parameter)
  - Tiki Vietnam    (affiliate deep-link via tracking parameter)

AccessTrade will be added later.

All public functions return a list of product dicts compatible with the
AffiliateLink TypedDict in state/pipeline_state.py.
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

import requests

from config.settings import (
    LAZADA_AFFILIATE_KEY,
    SHOPEE_AFFILIATE_ID,
    TIKI_AFFILIATE_KEY,
)

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 15  # seconds


# ── Shopee Vietnam ─────────────────────────────────────────────────────────────

def get_shopee_affiliate_link(keyword: str, limit: int = 3) -> list[dict[str, str]]:
    """
    Search Shopee Vietnam for products matching *keyword* and return affiliate links.

    Uses Shopee's public search endpoint to discover real product listings, then
    wraps each URL with the configured affiliate ID via the Shopee affiliate
    deep-link format.

    Args:
        keyword: Search term (Vietnamese or English).
        limit:   Maximum number of products to return (capped at 5).

    Returns:
        List of product dicts with keys: product_name, url, platform, price_range.
    """
    limit = min(limit, 5)
    search_url = "https://shopee.vn/api/v4/search/search_items"
    params: dict[str, Any] = {
        "by": "relevancy",
        "keyword": keyword,
        "limit": limit,
        "newest": 0,
        "order": "desc",
        "page_type": "search",
        "scenario": "PAGE_GLOBAL_SEARCH",
        "version": 2,
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://shopee.vn/",
    }

    results: list[dict[str, str]] = []
    try:
        resp = requests.get(
            search_url, params=params, headers=headers, timeout=_REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        items: list[dict] = resp.json().get("items") or []
    except Exception as exc:
        logger.warning("Shopee search failed for %r: %s", keyword, exc)
        return _shopee_fallback_search(keyword, limit)

    for item in items[:limit]:
        item_data = item.get("item_basic", item)
        name: str = item_data.get("name", "")
        shop_id: int = item_data.get("shopid", 0)
        item_id: int = item_data.get("itemid", 0)
        price_min: int = item_data.get("price_min", 0)
        price_max: int = item_data.get("price_max", 0)

        if not (name and shop_id and item_id):
            continue

        product_url = f"https://shopee.vn/product/{shop_id}/{item_id}"
        affiliate_url = _shopee_affiliate_wrap(product_url)

        price_range = _format_vnd_range(price_min // 100000, price_max // 100000)
        results.append(
            {
                "product_name": name,
                "url": affiliate_url,
                "platform": "shopee",
                "price_range": price_range,
            }
        )

    return results


def _shopee_affiliate_wrap(product_url: str) -> str:
    """Append Shopee affiliate tracking to a product URL."""
    if not SHOPEE_AFFILIATE_ID:
        return product_url
    return f"{product_url}?af_id={urllib.parse.quote(SHOPEE_AFFILIATE_ID)}"


def _shopee_fallback_search(keyword: str, limit: int) -> list[dict[str, str]]:
    """Return a search-result URL when the product API is unavailable."""
    encoded = urllib.parse.quote_plus(keyword)
    url = f"https://shopee.vn/search?keyword={encoded}"
    if SHOPEE_AFFILIATE_ID:
        url += f"&af_id={urllib.parse.quote(SHOPEE_AFFILIATE_ID)}"
    return [
        {
            "product_name": f"Tìm kiếm Shopee: {keyword}",
            "url": url,
            "platform": "shopee",
            "price_range": "Xem trên Shopee",
        }
    ][:limit]


# ── Lazada Vietnam ─────────────────────────────────────────────────────────────

def get_lazada_affiliate_link(keyword: str, limit: int = 3) -> list[dict[str, str]]:
    """
    Build Lazada Vietnam deep-link search URLs with affiliate tracking.

    Lazada's public affiliate programme appends `laz_trackingcode` to URLs.
    Without a server-side product API key, we return a tracked search URL.

    Args:
        keyword: Search term.
        limit:   Ignored (always returns one search link); kept for API symmetry.

    Returns:
        List with a single product dict pointing to a tracked search.
    """
    encoded = urllib.parse.quote_plus(keyword)
    base = f"https://www.lazada.vn/catalog/?q={encoded}"
    if LAZADA_AFFILIATE_KEY:
        base += f"&laz_trackingcode={urllib.parse.quote(LAZADA_AFFILIATE_KEY)}"
    return [
        {
            "product_name": f"Tìm kiếm Lazada: {keyword}",
            "url": base,
            "platform": "lazada",
            "price_range": "Xem trên Lazada",
        }
    ]


# ── Tiki Vietnam ───────────────────────────────────────────────────────────────

_TIKI_SEARCH_API = "https://tiki.vn/api/v2/products"


def get_tiki_affiliate_link(keyword: str, limit: int = 3) -> list[dict[str, str]]:
    """
    Search Tiki Vietnam for products and return affiliate-tagged URLs.

    Args:
        keyword: Search term (Vietnamese or English).
        limit:   Maximum number of products to return.

    Returns:
        List of product dicts with keys: product_name, url, platform, price_range.
    """
    limit = min(limit, 5)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://tiki.vn/",
    }
    try:
        resp = requests.get(
            _TIKI_SEARCH_API,
            params={"limit": limit, "q": keyword, "sort": "top_seller"},
            headers=headers,
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        products: list[dict] = resp.json().get("data", [])
    except Exception as exc:
        logger.warning("Tiki search failed for %r: %s", keyword, exc)
        return _tiki_fallback_search(keyword, limit)

    results: list[dict[str, str]] = []
    for product in products[:limit]:
        name: str = product.get("name", "")
        url_path: str = product.get("url_path") or product.get("url_key", "")
        price: int = product.get("price", 0)
        if not name:
            continue
        product_url = f"https://tiki.vn/{url_path}" if url_path else "https://tiki.vn/"
        affiliate_url = _tiki_affiliate_wrap(product_url)
        price_range = f"{price:,} VND".replace(",", ".") if price else "Xem trên Tiki"
        results.append(
            {
                "product_name": name,
                "url": affiliate_url,
                "platform": "tiki",
                "price_range": price_range,
            }
        )

    return results or _tiki_fallback_search(keyword, limit)


def _tiki_affiliate_wrap(product_url: str) -> str:
    if not TIKI_AFFILIATE_KEY:
        return product_url
    sep = "&" if "?" in product_url else "?"
    return f"{product_url}{sep}ref={urllib.parse.quote(TIKI_AFFILIATE_KEY)}"


def _tiki_fallback_search(keyword: str, limit: int) -> list[dict[str, str]]:
    encoded = urllib.parse.quote_plus(keyword)
    url = f"https://tiki.vn/search?q={encoded}"
    if TIKI_AFFILIATE_KEY:
        url += f"&ref={urllib.parse.quote(TIKI_AFFILIATE_KEY)}"
    return [
        {
            "product_name": f"Tìm kiếm Tiki: {keyword}",
            "url": url,
            "platform": "tiki",
            "price_range": "Xem trên Tiki",
        }
    ][:limit]


# ── Comment formatter ──────────────────────────────────────────────────────────

def format_affiliate_comment(products: list[dict[str, str]]) -> str:
    """
    Render a Vietnamese comment string that lists affiliate products.

    Intended to be posted as the first comment on a YouTube Short or
    Facebook Reel so the links appear without cluttering the main caption.

    Args:
        products: List of AffiliateLink dicts (from get_shopee_affiliate_link
                  or any other getter in this module).

    Returns:
        Formatted multi-line string ready to post as a comment.
        Returns an empty string if products is empty.
    """
    if not products:
        return ""

    lines: list[str] = [
        "🛒 Sản phẩm liên quan trong video:",
        "",
    ]
    platform_emoji = {
        "shopee": "🟠",
        "lazada": "🔵",
        "tiki": "🔴",
    }
    for product in products:
        name = product.get("product_name", "Sản phẩm")
        url = product.get("url", "")
        price = product.get("price_range", "")
        platform = product.get("platform", "")
        emoji = platform_emoji.get(platform, "🔗")
        price_str = f" — {price}" if price and "Xem" not in price else ""
        lines.append(f"{emoji} {name}{price_str}")
        if url:
            lines.append(f"   👉 {url}")
        lines.append("")

    lines.append("💡 Giá có thể thay đổi. Kiểm tra trước khi mua nhé!")
    return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_vnd_range(price_min_k: int, price_max_k: int) -> str:
    """Format a price range in thousands of VND (as returned by Shopee API)."""
    def fmt(val: int) -> str:
        # val is already in VND (after dividing by 100000 in caller)
        if val >= 1000:
            return f"{val // 1000}.{(val % 1000) // 100:01d} triệu VND"
        return f"{val:,} nghìn VND".replace(",", ".")

    if price_min_k == price_max_k or price_max_k == 0:
        return fmt(price_min_k)
    return f"{fmt(price_min_k)} – {fmt(price_max_k)}"
