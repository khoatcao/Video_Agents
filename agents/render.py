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

    if not scene_plan:
        err = "scene_plan is empty — cannot determine total_frames for render."
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}

    # ── 1. Calculate total frames ──────────────────────────────────────────────
    total_frames: int = sum(
        scene.get("duration_frames", 0) for scene in scene_plan
    )
    if total_frames <= 0:
        err = f"total_frames={total_frames} is invalid."
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}

    # ── 2. Build output path ───────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mp4_path = str(OUTPUT_DIR / f"{slot}_{timestamp}.mp4")

    # ── 3. Build scene_data payload ────────────────────────────────────────────
    scene_data = {
        "outputPath": mp4_path,
        "compositionFile": _COMPOSITION_ID,
        "durationInFrames": total_frames,
    }
    scene_data_json = json.dumps(scene_data)

    cmd = ["npx", "ts-node", "render.ts", "--scene-data", scene_data_json]
    logger.info(
        "[RenderAgent] Rendering %d frames → %s",
        total_frames,
        mp4_path,
    )
    logger.debug("[RenderAgent] Command: %s", " ".join(cmd))

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
        err = f"npx/ts-node not found: {exc}. Ensure Node.js is installed."
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}

    # Log stderr progress output (render.ts writes progress there)
    if result.stderr:
        for line in result.stderr.splitlines():
            logger.debug("[RenderAgent/ts-node] %s", line)

    if result.returncode != 0:
        stderr_tail = result.stderr[-2000:] if result.stderr else "<no stderr>"
        err = f"render.ts exited with code {result.returncode}. stderr:\n{stderr_tail}"
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}

    # render.ts prints the resolved output path on stdout
    resolved_path = result.stdout.strip() or mp4_path
    if not Path(resolved_path).is_file():
        err = f"Render succeeded but output file not found: {resolved_path}"
        logger.error("[RenderAgent] %s", err)
        return {"error": err, "status": "failed"}

    logger.info("[RenderAgent] Render complete → %s", resolved_path)
    return {
        "mp4_path": resolved_path,
        "error": None,
    }
