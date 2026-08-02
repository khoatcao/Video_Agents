"""
Phase 1 test: search → content → remotion → render

Runs the pipeline without any upload agents (no YouTube/Facebook needed).
Prints each step result and saves the final MP4 to outputs/.

Usage:
    python test_phase1.py
    python test_phase1.py --topic "LangGraph là gì" --slot morning
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("test_phase1")


def run(topic: str, slot: str) -> None:
    # ── Step 1: Web search ────────────────────────────────────────────────────
    logger.info("=== STEP 1: Web Search ===")
    from tools.web_search import search_trending_ai_topics
    search_result = search_trending_ai_topics.invoke(
        {"query": f"trending AI agents {topic} Vietnam 2024", "max_results": 5}
    )
    logger.info("Search results:\n%s\n", search_result[:800])

    # ── Step 2: Content Agent ─────────────────────────────────────────────────
    logger.info("=== STEP 2: Content Agent ===")
    from state.pipeline_state import create_initial_state
    state = create_initial_state(topic, slot)

    from agents.content import content_node
    content_update = content_node(state)
    state.update(content_update)

    logger.info("Scene plan (%d scenes):", len(state.get("scene_plan", [])))
    for scene in state.get("scene_plan", []):
        logger.info(
            "  Scene %s — %s frames — %s",
            scene.get("scene_num"),
            scene.get("duration_frames"),
            scene.get("text_overlay", "")[:60],
        )

    logger.info("\nYouTube title: %s", state.get("youtube_metadata", {}).get("title", ""))
    logger.info("Facebook caption: %s\n", state.get("facebook_metadata", {}).get("caption", "")[:120])

    if state.get("error"):
        logger.error("Content agent failed: %s", state["error"])
        sys.exit(1)

    # ── Step 3: Remotion Agent ────────────────────────────────────────────────
    logger.info("=== STEP 3: Remotion Agent (generates TSX) ===")
    from agents.remotion_agent import remotion_node
    remotion_update = remotion_node(state)
    state.update(remotion_update)

    if state.get("error"):
        logger.error("Remotion agent failed: %s", state["error"])
        sys.exit(1)

    tsx_path = state.get("remotion_project_path", "")
    logger.info("Generated TSX: %s", tsx_path)
    if tsx_path and Path(tsx_path).exists():
        size = Path(tsx_path).stat().st_size
        logger.info("TSX file size: %d bytes\n", size)

    # ── Step 4: Render Agent ──────────────────────────────────────────────────
    logger.info("=== STEP 4: Render Agent (renders MP4) ===")
    logger.info("This may take 1-3 minutes depending on scene count...")
    from agents.render import render_node
    render_update = render_node(state)
    state.update(render_update)

    if state.get("error"):
        logger.error("Render agent failed: %s", state["error"])
        sys.exit(1)

    mp4_path = state.get("mp4_path", "")
    logger.info("Rendered MP4: %s", mp4_path)
    if mp4_path and Path(mp4_path).exists():
        size_mb = Path(mp4_path).stat().st_size / (1024 * 1024)
        logger.info("MP4 file size: %.2f MB\n", size_mb)

    # ── Done ──────────────────────────────────────────────────────────────────
    logger.info("=== PHASE 1 COMPLETE ===")
    logger.info("MP4 saved to: %s", mp4_path)
    logger.info("Open the file to verify the video looks correct before Phase 2.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="AI Agent", help="Video topic")
    parser.add_argument(
        "--slot", default="morning", choices=["morning", "afternoon", "evening"]
    )
    args = parser.parse_args()
    run(args.topic, args.slot)
