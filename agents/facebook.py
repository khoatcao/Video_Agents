"""
Facebook Agent node for the LangGraph video-generation pipeline.

Responsibilities:
  1. Use qwen2.5:7b to craft a polished, engaging caption for the Reel,
     weaving in affiliate product teaser text and hashtags.
  2. Call upload_facebook_reel() to publish the MP4.
  3. Return facebook_post_id and facebook_url in the state update.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config.settings import FACEBOOK_ACCESS_TOKEN, FACEBOOK_PAGE_ID, MODEL_FAST, OLLAMA_BASE_URL
from state.pipeline_state import PipelineState
from tools.audio import mix_music
from tools.facebook_api import upload_facebook_reel

logger = logging.getLogger(__name__)

_FACEBOOK_CAPTION_PROMPT = """\
Bạn là chuyên gia content cho trang Facebook về AI và công nghệ tại Việt Nam.
Nhận vào thông tin về video và danh sách sản phẩm affiliate liên quan.
Viết một caption cho Facebook Reels:
  - Dòng đầu: câu hook gây tò mò (tối đa 125 ký tự — hiển thị trước "Xem thêm").
  - Thân bài: 2–4 đoạn, giải thích ngắn gọn nội dung video, tại sao nên xem.
  - KHÔNG đặt URL affiliate vào caption — hệ thống sẽ tự append sau.
  - Kết thúc bằng hashtags (tối đa 1500 ký tự — để dành chỗ cho affiliate links).
Trả về **đúng một đối tượng JSON** với key "caption" (string).
Chỉ trả về JSON. Không giải thích.
"""


def _strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _safe_extract_caption(text: str) -> str | None:
    """Return caption string from JSON response, or None on failure."""
    text = _strip_think_tags(text)
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("caption"):
            return str(data["caption"])
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict) and data.get("caption"):
                return str(data["caption"])
        except json.JSONDecodeError:
            pass
    return None


def _build_fallback_caption(state: PipelineState) -> str:
    """Build a minimal caption from existing state if LLM fails."""
    fb_meta = state.get("facebook_metadata", {})
    caption = fb_meta.get("caption", "")
    hashtags = fb_meta.get("hashtags", [])
    if not caption:
        caption = state.get("topic", "Video AI mới")
    if hashtags:
        caption += "\n\n" + " ".join(hashtags)
    if state.get("affiliate_links"):
        caption += "\n\n👇 Link sản phẩm trong comment đầu tiên"
    return caption[:2200]


def facebook_node(state: PipelineState) -> dict:
    """
    LangGraph node: craft caption and upload the Reel to Facebook.

    Reads:
        state["mp4_path"], state["facebook_metadata"], state["affiliate_links"]

    Writes:
        facebook_post_id, facebook_url
        — or —
        error, status (on failure)
    """
    vi_mp4_path: str = state.get("vi_mp4_path", "")
    mp4_path: str = vi_mp4_path if vi_mp4_path else state.get("mp4_path", "")
    facebook_metadata: dict = state.get("facebook_metadata", {})
    affiliate_links: list = state.get("affiliate_links", [])

    if vi_mp4_path:
        logger.info("[FacebookAgent] Using Vietnamese video for Facebook Reel.")
    else:
        logger.info("[FacebookAgent] vi_mp4_path not available — falling back to English video.")

    if not FACEBOOK_ACCESS_TOKEN:
        logger.info("[FacebookAgent] FACEBOOK_ACCESS_TOKEN not set — skipping upload.")
        return {"facebook_post_id": "", "facebook_url": ""}

    if not mp4_path:
        err = "mp4_path is empty — cannot upload to Facebook."
        logger.error("[FacebookAgent] %s", err)
        return {"error": err, "status": "failed"}

    # ── 1. Craft caption with qwen2.5:7b ──────────────────────────────────────
    llm = ChatOllama(
        model=MODEL_FAST,
        base_url=OLLAMA_BASE_URL,
        temperature=0.6,
        format="json",
    )

    affiliate_summary = (
        json.dumps(
            [{"product_name": p.get("product_name", ""), "platform": p.get("platform", "")}
             for p in affiliate_links],
            ensure_ascii=False,
        )
        if affiliate_links
        else "[]"
    )

    human_message = (
        f"Thông tin Facebook Reels:\n"
        f"Caption gốc: {facebook_metadata.get('caption', '')}\n"
        f"Hashtags: {' '.join(facebook_metadata.get('hashtags', []))}\n\n"
        f"Sản phẩm affiliate liên quan (chỉ teaser, KHÔNG đặt URL vào caption):\n"
        f"{affiliate_summary}\n\n"
        "Viết caption tối ưu và trả về JSON với key 'caption'."
    )

    messages = [
        SystemMessage(content=_FACEBOOK_CAPTION_PROMPT),
        HumanMessage(content=human_message),
    ]

    logger.info("[FacebookAgent] Crafting caption with %s …", MODEL_FAST)
    full_caption: str = ""
    try:
        response = llm.invoke(messages)
        raw_content: str = response.content if hasattr(response, "content") else str(response)
        full_caption = _safe_extract_caption(raw_content) or ""
        if full_caption:
            logger.debug("[FacebookAgent] Caption crafted successfully.")
        else:
            logger.warning("[FacebookAgent] LLM returned no caption; using fallback.")
    except Exception as exc:
        logger.warning("[FacebookAgent] Caption generation failed: %s — using fallback.", exc)

    if not full_caption:
        full_caption = _build_fallback_caption(state)

    # Always ensure hashtags are appended — LLM sometimes omits them
    hashtags: list = facebook_metadata.get("hashtags", [])
    if hashtags:
        hashtag_str = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags)
        if hashtag_str not in full_caption:
            full_caption = full_caption.rstrip() + "\n\n" + hashtag_str

    # Append affiliate links directly in caption
    if affiliate_links:
        aff_lines = ["\n\n🛒 Link sản phẩm:"]
        for p in affiliate_links:
            url = p.get("url", "")
            if url:
                aff_lines.append(f"👉 {url}")
        full_caption = full_caption.rstrip() + "\n".join(aff_lines)

    # Append source link for credibility
    source: str = state.get("source", "")
    source_url: str = state.get("source_url", "")
    if source or source_url:
        source_block = "\n\n📰 Nguồn:"
        if source:
            source_block += f" {source}"
        if source_url:
            source_block += f"\n🔗 {source_url}"
        full_caption = full_caption.rstrip() + source_block

    # Truncate — keep under 2000 chars to avoid API payload errors
    if len(full_caption) > 2000:
        full_caption = full_caption[:1997] + "..."

    # ── 2. Mix Facebook Sound Collection music ────────────────────────────────
    upload_path = mix_music(mp4_path, platform="facebook")

    # ── 3. Upload Reel to Facebook ─────────────────────────────────────────────
    logger.info("[FacebookAgent] Uploading %s to Facebook …", upload_path)
    try:
        post_id, video_id = upload_facebook_reel(mp4_path=upload_path, caption=full_caption)
    except FileNotFoundError as exc:
        err = str(exc)
        logger.error("[FacebookAgent] %s", err)
        return {"error": err, "status": "failed"}
    except Exception as exc:
        err = f"Facebook upload failed: {exc}"
        logger.error("[FacebookAgent] %s", err)
        return {"error": err, "status": "failed"}

    facebook_url = f"https://www.facebook.com/{FACEBOOK_PAGE_ID}/videos/{video_id}"
    logger.info("[FacebookAgent] Reel published → post_id=%s  video_id=%s  url=%s", post_id, video_id, facebook_url)
    return {
        "facebook_post_id": post_id,
        "facebook_video_id": video_id,
        "facebook_url": facebook_url,
    }
