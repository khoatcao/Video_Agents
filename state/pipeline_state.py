"""
Shared pipeline state for the video-agent LangGraph workflow.

All eight agents read from and write to this single TypedDict so that
LangGraph can checkpoint, resume, and branch the workflow without any
agent needing its own persistence layer.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


class ScenePlan(TypedDict):
    scene_num: int
    duration_frames: int       # 30 fps → 90 frames = 3 seconds
    description: str
    text_overlay: str          # Vietnamese copy shown on screen
    visual_type: str           # "diagram" | "text" | "flow_chart" | "comparison"


class YouTubeMetadata(TypedDict):
    title: str
    description: str
    tags: List[str]
    category_id: str           # "28" = Science & Technology


class FacebookMetadata(TypedDict):
    caption: str
    hashtags: List[str]


class AffiliateLink(TypedDict):
    product_name: str
    url: str
    platform: str              # "shopee" | "accesstrade" | "lazada" | "tiki"
    price_range: str           # e.g. "500.000 – 1.200.000 VND"


class PipelineState(TypedDict):
    # ── Input ────────────────────────────────────────────────────────────────
    topic: str
    slot: str                       # "morning" | "afternoon" | "evening"

    # ── Content planning ─────────────────────────────────────────────────────
    scene_plan: List[ScenePlan]
    youtube_metadata: YouTubeMetadata
    facebook_metadata: FacebookMetadata

    # ── Rendering ────────────────────────────────────────────────────────────
    remotion_project_path: str      # path to generated .tsx file
    mp4_path: str                   # path to rendered MP4

    # ── Monetisation ─────────────────────────────────────────────────────────
    affiliate_links: List[AffiliateLink]

    # ── Distribution ─────────────────────────────────────────────────────────
    youtube_url: str
    facebook_post_id: str
    facebook_url: str

    # ── Workflow control ──────────────────────────────────────────────────────
    error: Optional[str]
    retry_count: int
    status: str                     # "running" | "completed" | "failed"
    messages: List[BaseMessage]     # LangChain message history for all agents


def create_initial_state(topic: str, slot: str) -> PipelineState:
    """
    Return a PipelineState populated with safe defaults.

    All agents expect every key to exist so they can safely read fields
    without KeyError even on the first pass through the graph.

    Args:
        topic: The AI/tech topic for this video (e.g. "LangGraph multi-agent").
        slot:  Scheduling slot — "morning", "afternoon", or "evening".

    Returns:
        A fully initialised PipelineState ready to hand to the LangGraph runner.
    """
    if slot not in ("morning", "afternoon", "evening", "night"):
        raise ValueError(f"slot must be 'morning', 'afternoon', 'evening', or 'night'; got {slot!r}")
    if not topic.strip():
        raise ValueError("topic must be a non-empty string")

    return PipelineState(
        topic=topic.strip(),
        slot=slot,
        scene_plan=[],
        youtube_metadata=YouTubeMetadata(
            title="",
            description="",
            tags=[],
            category_id="28",
        ),
        facebook_metadata=FacebookMetadata(
            caption="",
            hashtags=[],
        ),
        remotion_project_path="",
        mp4_path="",
        affiliate_links=[],
        youtube_url="",
        facebook_post_id="",
        facebook_url="",
        error=None,
        retry_count=0,
        status="running",
        messages=[],
    )
