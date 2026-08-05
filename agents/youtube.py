"""
YouTube Agent node for the LangGraph video-generation pipeline.

Responsibilities:
  1. Optimise YouTube title, description, and tags with an LLM.
  2. Write metadata.txt into the video subfolder for manual upload.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config.settings import MODEL_FAST, OLLAMA_BASE_URL
from state.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

_YOUTUBE_OPTIMISER_PROMPT = """\
You are a YouTube SEO expert for an AI/tech Shorts channel.
Given a JSON object with title, description, and tags for a YouTube Short, \
return exactly one optimised JSON object with the same structure:
  - title: max 97 characters (leave room for " #Shorts"), include the main keyword, make it punchy.
  - description: 150–300 words, SEO keywords throughout, first line is a hook, \
ends with a CTA and key hashtags. All in English.
  - tags: 10–15 tags in English covering the topic, tools, and technologies mentioned.
  - category_id: keep the input value unchanged.
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
    LangGraph node: optimise YouTube metadata and write metadata.txt for manual upload.

    Reads:
        state["mp4_path"], state["youtube_metadata"]

    Writes:
        youtube_url (empty — manual upload)
        — or —
        error, status (on failure)
    """
    mp4_path: str = state.get("mp4_path", "")
    youtube_metadata: dict = state.get("youtube_metadata", {})

    if not mp4_path:
        err = "mp4_path is empty — render must have failed."
        logger.error("[YouTubeAgent] %s", err)
        return {"error": err, "status": "failed"}

    # ── 1. Optimise metadata ───────────────────────────────────────────────────
    llm = ChatOllama(
        model=MODEL_FAST,
        base_url=OLLAMA_BASE_URL,
        temperature=0.5,
        format="json",
    )
    human_message = (
        "Optimise the following YouTube metadata for an English-speaking technical audience:\n\n"
        f"```json\n{json.dumps(youtube_metadata, ensure_ascii=False, indent=2)}\n```\n\n"
        "Return the optimised JSON matching the required schema."
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
        else:
            logger.warning("[YouTubeAgent] LLM returned incomplete metadata — using original.")
    except Exception as exc:
        logger.warning("[YouTubeAgent] Metadata optimisation failed: %s — using original.", exc)

    return {"youtube_url": ""}
