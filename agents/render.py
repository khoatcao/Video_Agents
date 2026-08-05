"""
Render Agent node for the LangGraph video-generation pipeline.

Responsibilities:
  1. Calculate total_frames from scene_plan.
  2. Invoke the Remotion render pipeline via ts-node render.ts (subprocess).
  3. Capture stdout (the resolved output path) and stderr (progress logs).
  4. Return mp4_path on success, or error/status on failure.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

from config.settings import OUTPUT_DIR
from state.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# Absolute path to the remotion project root so subprocess CWD is correct.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REMOTION_DIR = _PROJECT_ROOT / "remotion"

# Remotion composition ID (must match the id= in <Composition … /> in Root.tsx)
_COMPOSITION_ID = "VideoComposition"

# Maximum time (seconds) to wait for the render subprocess.
_RENDER_TIMEOUT = 600


def render_node(state: PipelineState) -> dict:
    """
    LangGraph node: render the Remotion project to an MP4 file.

    Reads:
        state["scene_plan"], state["slot"], state["remotion_project_path"]

    Writes (returned dict merged into PipelineState by LangGraph):
        mp4_path
        — or —
        error, status (on failure)
    """
    scene_plan = state.get("scene_plan", [])
    slot: str = state.get("slot", "morning")
    topic: str = state.get("topic", "")
    source: str = state.get("source", "")
    source_url: str = state.get("source_url", "")
    youtube_metadata: dict = state.get("youtube_metadata", {})

    if not scene_plan:
        err = "scene_plan is empty — cannot determine total_frames for render."
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}

    # ── 1. Calculate total frames from validated scene_plan ───────────────────
    # Note: remotion_agent may have scaled duration_frames during validation.
    # We use scene_plan here only for a basic sanity check; the actual render
    # duration comes from TOTAL_FRAMES exported by VideoComposition.tsx.
    total_frames: int = sum(
        scene.get("duration_frames", 0) for scene in scene_plan
    )
    if total_frames <= 0:
        err = f"total_frames={total_frames} is invalid."
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}
    logger.info("[RenderAgent] scene_plan frames=%d (actual TSX duration may differ after validation)", total_frames)

    # ── 2. Build output path ───────────────────────────────────────────────────
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:50]
    source_slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")[:20] if source else ""
    name = f"{date_str}_{source_slug}_{topic_slug}" if source_slug else f"{date_str}_{topic_slug}"
    video_dir = OUTPUT_DIR / name
    video_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = str(video_dir / f"{name}.mp4")

    # ── 3. Build scene_data payload ────────────────────────────────────────────
    scene_data = {
        "outputPath": mp4_path,
        "compositionFile": _COMPOSITION_ID,
        "durationInFrames": total_frames,
    }
    scene_data_json = json.dumps(scene_data)

    # Root.tsx imports TOTAL_FRAMES from VideoComposition.tsx, so durationInFrames
    # is always correct. No --frames flag needed — Remotion renders all frames.
    cmd = [
        "npx", "remotion", "render",
        "src/index.ts",
        _COMPOSITION_ID,
        mp4_path,
        "--codec=h264",
        "--image-format=jpeg",
        "--overwrite",
    ]
    logger.info("[RenderAgent] Rendering %d frames → %s", total_frames, mp4_path)
    logger.info("[RenderAgent] Command: %s", " ".join(cmd))

    # ── 4. Run subprocess ──────────────────────────────────────────────────────
    try:
        result = subprocess.run(
            cmd,
            cwd=str(_REMOTION_DIR),
            capture_output=True,
            text=True,
            timeout=_RENDER_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        err = f"Remotion render timed out after {_RENDER_TIMEOUT}s."
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}
    except FileNotFoundError as exc:
        err = f"npx not found: {exc}. Ensure Node.js is installed and npm install has been run."
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}

    # Log stderr — always at INFO so render progress is visible
    if result.stderr:
        for line in result.stderr.splitlines():
            logger.info("[RenderAgent/ts-node] %s", line)

    if result.returncode != 0:
        stderr_tail = result.stderr[-3000:] if result.stderr else "<no stderr>"
        err = f"render.ts exited with code {result.returncode}.\n{stderr_tail}"
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}

    # Remotion CLI writes to the path we specified — just verify it exists
    resolved_path = mp4_path
    if not Path(resolved_path).is_file():
        err = f"Render succeeded but output file not found: {resolved_path}"
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}

    logger.info("[RenderAgent] Render complete → %s", resolved_path)

    # ── 5. Write metadata.txt alongside the video ─────────────────────────────
    title = youtube_metadata.get("title", topic)
    description = youtube_metadata.get("description", "")
    vi_title = youtube_metadata.get("vi_title", "")
    vi_description = youtube_metadata.get("vi_description", "")
    tags: list = youtube_metadata.get("tags", [])
    hashtags = " ".join(f"#{t.lstrip('#')}" for t in tags)

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
        (Path(resolved_path).parent / "metadata.txt").write_text(metadata, encoding="utf-8")
        logger.info("[RenderAgent] metadata.txt written → %s", Path(resolved_path).parent)
    except Exception as exc:
        logger.warning("[RenderAgent] Could not write metadata.txt: %s", exc)

    return {
        "mp4_path": resolved_path,
        "error": None,
    }
