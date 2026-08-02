"""
Content Agent node for the LangGraph video-generation pipeline.

Responsibilities:
  1. Search for trending AI/tech articles via DuckDuckGo.
  2. Prompt qwen2.5:7b (via Ollama) with the CONTENT_AGENT_SYSTEM_PROMPT.
  3. Parse the JSON response into scene_plan, youtube_metadata, facebook_metadata.
  4. Return a partial state dict for LangGraph to merge into PipelineState.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config.prompts.content_agent import CONTENT_AGENT_SYSTEM_PROMPT
from config.settings import MODEL_REASONING, OLLAMA_BASE_URL
from state.pipeline_state import PipelineState
from tools.web_search import search_trending_ai_topics

logger = logging.getLogger(__name__)


def _strip_think_tags(text: str) -> str:
    """Remove <think>…</think> reasoning blocks emitted by deepseek-r1 models."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json(text: str) -> Any:
    """
    Extract the first JSON object or array from *text*.

    Tries a direct parse first; if that fails, searches for the first
    '{' or '[' and tries from there.
    """
    text = _strip_think_tags(text)

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first JSON boundary
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        if start == -1:
            continue
        # Walk backwards from end to find matching closer
        end = text.rfind(end_char)
        if end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"No valid JSON found in response:\n{text[:500]}")


def content_node(state: PipelineState) -> dict:
    """
    LangGraph node: plan the video content for the given topic and slot.

    Reads:
        state["topic"], state["slot"]

    Writes (returned dict merged into PipelineState by LangGraph):
        scene_plan, youtube_metadata, facebook_metadata
        — or —
        error, status (on failure)
    """
    topic: str = state["topic"]
    slot: str = state["slot"]

    # ── 1. Web search for trending context ────────────────────────────────────
    search_query = f"trending AI agents {topic} Vietnam"
    logger.info("[ContentAgent] Searching DuckDuckGo: %r", search_query)
    try:
        search_results: str = search_trending_ai_topics.invoke(
            {"query": search_query, "max_results": 5}
        )
    except Exception as exc:
        logger.warning("[ContentAgent] DuckDuckGo search failed: %s — continuing without results", exc)
        search_results = "Search unavailable."

    # ── 2. Build LLM prompt ────────────────────────────────────────────────────
    llm = ChatOllama(
        model=MODEL_REASONING,
        base_url=OLLAMA_BASE_URL,
        temperature=0.7,
        format="json",
    )
    llm_with_tools = llm.bind_tools([search_trending_ai_topics])

    human_message = (
        f"Chủ đề video: {topic}\n"
        f"Khung giờ đăng: {slot}\n\n"
        f"--- Kết quả tìm kiếm xu hướng ---\n{search_results}\n"
        f"---------------------------------\n\n"
        "Hãy tạo kịch bản video theo schema JSON đã quy định."
    )

    messages = [
        SystemMessage(content=CONTENT_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=human_message),
    ]

    logger.info("[ContentAgent] Invoking %s …", MODEL_REASONING)
    try:
        response = llm_with_tools.invoke(messages)
        raw_content: str = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("[ContentAgent] LLM call failed: %s", exc)
        return {"error": str(exc), "status": "failed"}

    # ── 3. Parse JSON response ─────────────────────────────────────────────────
    try:
        data = _extract_json(raw_content)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("[ContentAgent] JSON parse failed: %s\nRaw response:\n%s", exc, raw_content[:1000])
        return {"error": f"JSON parse error: {exc}", "status": "failed"}

    # Validate required keys
    missing = [k for k in ("scene_plan", "youtube_metadata", "facebook_metadata") if k not in data]
    if missing:
        err = f"LLM response missing keys: {missing}"
        logger.error("[ContentAgent] %s", err)
        return {"error": err, "status": "failed"}

    scene_plan = data["scene_plan"]
    youtube_metadata = data["youtube_metadata"]
    facebook_metadata = data["facebook_metadata"]

    # Ensure category_id has the right default
    if "category_id" not in youtube_metadata:
        youtube_metadata["category_id"] = "28"

    logger.info(
        "[ContentAgent] Done. %d scenes, title=%r",
        len(scene_plan),
        youtube_metadata.get("title", ""),
    )

    return {
        "scene_plan": scene_plan,
        "youtube_metadata": youtube_metadata,
        "facebook_metadata": facebook_metadata,
        "error": None,
    }
