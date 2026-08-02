"""
YouTube Agent node for the LangGraph video-generation pipeline.

Responsibilities:
  1. Use qwen2.5:7b to optimise the YouTube title and description for a
     Vietnamese-speaking technical audience (SEO-friendly, correct length).
  2. Call upload_youtube_short() to publish the MP4 as a Short.
  3. Return the public YouTube URL in the state update.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config.settings import MODEL_FAST, OLLAMA_BASE_URL, YOUTUBE_CLIENT_ID
from state.pipeline_state import PipelineState
from tools.youtube_api import upload_youtube_short

logger = logging.getLogger(__name__)

_YOUTUBE_OPTIMISER_PROMPT = """\
Bạn là chuyên gia SEO YouTube cho kênh công nghệ/AI tại Việt Nam.
Nhận vào JSON chứa title, description và tags của một video Shorts.
Trả về **đúng một đối tượng JSON** với cùng cấu trúc nhưng đã được tối ưu:
  - title: tối đa 97 ký tự (để chừa chỗ cho " #Shorts"), chứa từ khoá chính, hấp dẫn.
  - description: 150–300 từ, có từ khoá SEO, dòng đầu tiên là câu hook, \
kết thúc bằng CTA và các hashtag chính.
  - tags: danh sách 10–15 tag, gồm cả tiếng Việt và tiếng Anh.
  - category_id: giữ nguyên giá trị đầu vào.
Chỉ trả về JSON. Không giải thích.
"""


def _strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _safe_extract_json(text: str) -> dict[str, Any]:
    """Return the first JSON object found in *text*, or {} on failure."""
    text = _strip_think_tags(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def youtube_node(state: PipelineState) -> dict:
    """
    LangGraph node: optimise YouTube metadata and upload the Short.

    Reads:
        state["mp4_path"], state["youtube_metadata"]

    Writes:
        youtube_url
        — or —
        error, status (on failure)
    """
    mp4_path: str = state.get("mp4_path", "")
    youtube_metadata: dict = state.get("youtube_metadata", {})

    if not YOUTUBE_CLIENT_ID:
        logger.info("[YouTubeAgent] YOUTUBE_CLIENT_ID not set — skipping upload.")
        return {"youtube_url": "", "error": None}

    if not mp4_path:
        err = "mp4_path is empty — cannot upload to YouTube."
        logger.error("[YouTubeAgent] %s", err)
        return {"error": err, "status": "failed"}

    # ── 1. Optimise metadata with qwen2.5:7b ───────────────────────────────────
    llm = ChatOllama(
        model=MODEL_FAST,
        base_url=OLLAMA_BASE_URL,
        temperature=0.5,
        format="json",
    )

    human_message = (
        "Tối ưu hoá metadata YouTube sau đây cho khán giả kỹ thuật Việt Nam:\n\n"
        f"```json\n{json.dumps(youtube_metadata, ensure_ascii=False, indent=2)}\n```\n\n"
        "Trả về JSON đã được tối ưu theo schema quy định."
    )

    messages = [
        SystemMessage(content=_YOUTUBE_OPTIMISER_PROMPT),
        HumanMessage(content=human_message),
    ]

    logger.info("[YouTubeAgent] Optimising metadata with %s …", MODEL_FAST)
    optimised: dict = youtube_metadata.copy()
    try:
        response = llm.invoke(messages)
        raw_content: str = response.content if hasattr(response, "content") else str(response)
        parsed = _safe_extract_json(raw_content)
        if parsed.get("title") and parsed.get("description"):
            optimised.update(parsed)
            logger.debug("[YouTubeAgent] Metadata optimised successfully.")
        else:
            logger.warning("[YouTubeAgent] LLM returned incomplete metadata; using original.")
    except Exception as exc:
        logger.warning("[YouTubeAgent] Metadata optimisation failed: %s — using original.", exc)

    title: str = optimised.get("title", "AI Video #Shorts")
    description: str = optimised.get("description", "")
    tags: list[str] = optimised.get("tags", [])
    category_id: str = str(optimised.get("category_id", "28"))

    # ── 2. Upload to YouTube ───────────────────────────────────────────────────
    logger.info("[YouTubeAgent] Uploading %s to YouTube …", mp4_path)
    try:
        youtube_url = upload_youtube_short(
            mp4_path=mp4_path,
            title=title,
            description=description,
            tags=tags,
            category_id=category_id,
        )
    except FileNotFoundError as exc:
        err = str(exc)
        logger.error("[YouTubeAgent] %s", err)
        return {"error": err, "status": "failed"}
    except Exception as exc:
        err = f"YouTube upload failed: {exc}"
        logger.error("[YouTubeAgent] %s", err)
        return {"error": err, "status": "failed"}

    logger.info("[YouTubeAgent] Upload complete → %s", youtube_url)
    return {"youtube_url": youtube_url, "error": None}
