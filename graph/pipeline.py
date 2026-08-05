"""
Main LangGraph pipeline for the video-generation system.

Active topology:
  START → content ──(retry loop)──► remotion ──(retry loop)──► render ──(retry loop)──► youtube → END

Disabled (re-enable when Facebook API is ready):
  render → affiliate_pre → facebook → affiliate_post → END

Retry loops: content_retry → content, remotion_retry → remotion, render_retry → render.
On exhausted retries, each node routes to fail_node → END.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from agents.content import content_node
# from agents.facebook import facebook_node          # disabled — re-enable when FB API ready
# from agents.affiliate import affiliate_pre_node, affiliate_post_node  # disabled
from agents.orchestrator import fail_node, handle_error, should_retry
from agents.remotion_agent import remotion_node
from agents.render import render_node
from agents.youtube import youtube_node
from state.pipeline_state import PipelineState, create_initial_state

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    # ── Register all nodes ─────────────────────────────────────────────────────
    graph.add_node("content", content_node)
    graph.add_node("content_retry", handle_error)

    graph.add_node("remotion", remotion_node)
    graph.add_node("remotion_retry", handle_error)

    graph.add_node("render", render_node)
    graph.add_node("render_retry", handle_error)

    graph.add_node("youtube", youtube_node)
    graph.add_node("fail", fail_node)

    # Disabled nodes — uncomment to re-enable Facebook posting:
    # graph.add_node("affiliate_pre", affiliate_pre_node)
    # graph.add_node("facebook", facebook_node)
    # graph.add_node("affiliate_post", affiliate_post_node)

    # ── Entry point ────────────────────────────────────────────────────────────
    graph.add_edge(START, "content")

    # ── Content node: conditional retry ───────────────────────────────────────
    graph.add_conditional_edges(
        "content",
        should_retry,
        {
            "retry": "content_retry",
            "fail": "fail",
            "continue": "remotion",
        },
    )
    graph.add_edge("content_retry", "content")

    # ── Remotion node: conditional retry ──────────────────────────────────────
    graph.add_conditional_edges(
        "remotion",
        should_retry,
        {
            "retry": "remotion_retry",
            "fail": "fail",
            "continue": "render",
        },
    )
    graph.add_edge("remotion_retry", "remotion")

    # ── Render node: conditional retry ────────────────────────────────────────
    graph.add_conditional_edges(
        "render",
        should_retry,
        {
            "retry": "render_retry",
            "fail": "fail",
            "continue": "youtube",
            # "continue": "affiliate_pre",  # swap this when re-enabling Facebook
        },
    )
    graph.add_edge("render_retry", "render")

    # ── YouTube → END (manual upload) ─────────────────────────────────────────
    graph.add_edge("youtube", END)

    # Disabled — Facebook routing (uncomment to re-enable):
    # graph.add_edge("affiliate_pre", "youtube")
    # graph.add_edge("affiliate_pre", "facebook")
    # graph.add_edge("youtube", END)
    # graph.add_edge("facebook", "affiliate_post")
    # graph.add_edge("affiliate_post", END)

    # ── Failure terminal ──────────────────────────────────────────────────────
    graph.add_edge("fail", END)

    return graph.compile()


def run_pipeline_graph(topic: str, slot: str) -> PipelineState:
    """
    Compile and run the full pipeline.

    Args:
        topic: AI/tech topic for the video (e.g. "LangGraph multi-agent").
        slot:  Scheduling slot — "morning", "afternoon", or "evening".

    Returns:
        Final PipelineState after all nodes have completed (or failed).
    """
    logger.info("[Pipeline] run_pipeline_graph: topic=%r  slot=%r", topic, slot)

    initial_state = create_initial_state(topic=topic, slot=slot)
    compiled = build_graph()

    final_state: PipelineState = compiled.invoke(initial_state)

    if final_state.get("status") == "running":
        final_state = dict(final_state)  # type: ignore[assignment]
        final_state["status"] = "completed"

    logger.info(
        "[Pipeline] Finished. status=%r  youtube_url=%r  facebook_url=%r",
        final_state.get("status"),
        final_state.get("youtube_url"),
        final_state.get("facebook_url"),
    )
    return final_state  # type: ignore[return-value]
