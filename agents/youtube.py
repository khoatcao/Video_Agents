"""
YouTube Agent node for the LangGraph video-generation pipeline.

Responsibilities:
  1. Call LLM once to optimise English metadata and generate Vietnamese translation.
  2. Write metadata.txt into the video subfolder for manual upload.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config.settings import MODEL_FAST, OLLAMA_BASE_URL, TEMPERATURE_METADATA
from state.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

_METADATA_PROMPT = """\
You are a YouTube SEO expert for an AI/tech Shorts channel.
Given a JSON object with a video title, description, and tags, return exactly one JSON object with:

  - title: optimised English title, max 97 chars, punchy, includes main keyword and emoji
  - description: 150-300 words in English, first line is a hook, ends with CTA and hashtags
  - tags: 10-15 English tags covering topic, tools, and technologies
  - category_id: keep the input value unchanged
  - vi_title: Vietnamese translation of the title, max 97 chars, natural and engaging
  - vi_description: Vietnamese translation of the description, 150-300 words, same structure

Return JSON only. No explanation.
"""


def _strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _safe_extract_json(text: str) -> dict[str, Any]:
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
    LangGraph node: optimise metadata in both English and Vietnamese,
    then write metadata.txt for manual upload.

    Reads:
        state["mp4_path"], state["youtube_metadata"], state["source"], state["source_url"]

    Writes:
        youtube_url (empty — manual upload)
    """
    mp4_path: str = state.get("mp4_path", "")
    youtube_metadata: dict = state.get("youtube_metadata", {})
    source: str = state.get("source", "")
    source_url: str = state.get("source_url", "")

    if not mp4_path:
        err = "mp4_path is empty — render must have failed."
        logger.error("[YouTubeAgent] %s", err)
        return {"error": err, "status": "failed"}

    # ── 1. Generate optimised EN + VI metadata in one LLM call ────────────────
    llm = ChatOllama(
        model=MODEL_FAST,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE_METADATA,
        format="json",
    )
    human_message = (
        "Optimise the following YouTube metadata and provide a Vietnamese translation:\n\n"
        f"```json\n{json.dumps(youtube_metadata, ensure_ascii=False, indent=2)}\n```\n\n"
        "Return the JSON with both English (title, description, tags) and "
        "Vietnamese (vi_title, vi_description) fields."
    )
    messages = [
        SystemMessage(content=_METADATA_PROMPT),
        HumanMessage(content=human_message),
    ]

    logger.info("[YouTubeAgent] Generating EN + VI metadata with %s …", MODEL_FAST)
    optimised: dict = youtube_metadata.copy()
    try:
        response = llm.invoke(messages)
        raw_content: str = response.content if hasattr(response, "content") else str(response)
        parsed = _safe_extract_json(raw_content)
        if parsed.get("title") and parsed.get("vi_title"):
            optimised.update(parsed)
        else:
            logger.warning("[YouTubeAgent] LLM returned incomplete metadata — using original.")
    except Exception as exc:
        logger.warning("[YouTubeAgent] Metadata generation failed: %s — using original.", exc)

    title: str = optimised.get("title", "")
    description: str = optimised.get("description", "")
    vi_title: str = optimised.get("vi_title", "")
    vi_description: str = optimised.get("vi_description", "")
    tags: list = optimised.get("tags", [])
    hashtags = " ".join(f"#{t.lstrip('#')}" for t in tags)

    # ── 2. Write metadata.txt ──────────────────────────────────────────────────
    lines = [
        "=" * 50,
        "ENGLISH",
        "=" * 50,
        f"Title: {title} #Shorts",
        "",
        "Description:",
        description,
        "",
        "Hashtags:",
        hashtags,
        "",
        "=" * 50,
        "VIETNAMESE",
        "=" * 50,
        f"Tiêu đề: {vi_title} #Shorts",
        "",
        "Mô tả:",
        vi_description,
        "",
    ]
    if source:
        lines.append(f"Source: {source}")
    if source_url:
        lines.append(f"URL: {source_url}")

    metadata = "\n".join(lines)
    try:
        video_dir = Path(mp4_path).parent
        (video_dir / "metadata.txt").write_text(metadata, encoding="utf-8")
        logger.info("[YouTubeAgent] metadata.txt written → %s", video_dir)
    except Exception as exc:
        logger.warning("[YouTubeAgent] Could not write metadata.txt: %s", exc)

    return {"youtube_url": ""}
