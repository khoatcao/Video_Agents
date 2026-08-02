"""
Remotion Agent node for the LangGraph video-generation pipeline.

Responsibilities:
  1. Receive scene_plan from PipelineState.
  2. Prompt deepseek-coder:6.7b to generate a complete VideoComposition.tsx.
  3. Extract the TypeScript source from the LLM response.
  4. Write it to OUTPUT_DIR/compositions/ (timestamped archive) AND
     overwrite remotion/src/compositions/VideoComposition.tsx for rendering.
  5. Return remotion_project_path in the state update.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config.prompts.remotion_agent import REMOTION_AGENT_SYSTEM_PROMPT
from config.settings import MODEL_CODE, OLLAMA_BASE_URL, OUTPUT_DIR
from state.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# Absolute path to the live Remotion composition file that render.ts reads.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REMOTION_LIVE_PATH = _PROJECT_ROOT / "remotion" / "src" / "compositions" / "VideoComposition.tsx"


def _extract_tsx(text: str) -> str:
    """
    Extract TypeScript/TSX source code from the LLM response.

    Priority:
      1. Content between ```tsx … ``` fences.
      2. Content between ```typescript … ``` fences.
      3. Content between ``` … ``` fences.
      4. Raw text if it starts with 'import' (no fence at all).
    """
    # Try tsx fence
    m = re.search(r"```tsx\s*([\s\S]+?)```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Try typescript fence
    m = re.search(r"```typescript\s*([\s\S]+?)```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Try generic fence
    m = re.search(r"```\s*([\s\S]+?)```", text)
    if m:
        return m.group(1).strip()

    # Raw TypeScript (no fence) — accept if it looks like TS
    stripped = text.strip()
    if stripped.startswith("import") or stripped.startswith("//"):
        return stripped

    raise ValueError(
        "Could not extract TypeScript code from LLM response. "
        f"First 300 chars:\n{text[:300]}"
    )


def remotion_node(state: PipelineState) -> dict:
    """
    LangGraph node: generate the Remotion VideoComposition.tsx from scene_plan.

    Reads:
        state["scene_plan"]

    Writes (returned dict merged into PipelineState by LangGraph):
        remotion_project_path
        — or —
        error, status (on failure)
    """
    scene_plan = state.get("scene_plan", [])
    if not scene_plan:
        err = "scene_plan is empty — cannot generate Remotion composition."
        logger.error("[RemotionAgent] %s", err)
        return {"error": err, "status": "failed"}

    # ── 1. Build prompt ────────────────────────────────────────────────────────
    scene_json = json.dumps(scene_plan, ensure_ascii=False, indent=2)
    human_message = (
        f"Generate the VideoComposition.tsx for the following scene plan:\n\n"
        f"```json\n{scene_json}\n```\n\n"
        "Return only the complete TypeScript source inside a tsx code fence."
    )

    llm = ChatOllama(
        model=MODEL_CODE,
        base_url=OLLAMA_BASE_URL,
        temperature=0.2,  # Low temperature for deterministic code generation
    )

    messages = [
        SystemMessage(content=REMOTION_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=human_message),
    ]

    logger.info("[RemotionAgent] Invoking %s for %d scenes …", MODEL_CODE, len(scene_plan))
    try:
        response = llm.invoke(messages)
        raw_content: str = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("[RemotionAgent] LLM call failed: %s", exc)
        return {"error": str(exc), "status": "failed"}

    # ── 2. Extract TypeScript code ─────────────────────────────────────────────
    try:
        tsx_code = _extract_tsx(raw_content)
    except ValueError as exc:
        logger.error("[RemotionAgent] %s", exc)
        return {"error": str(exc), "status": "failed"}

    # Basic sanity check: the file should export VideoComposition
    if "VideoComposition" not in tsx_code:
        err = "Generated TSX does not contain 'VideoComposition' export."
        logger.error("[RemotionAgent] %s", err)
        return {"error": err, "status": "failed"}

    # ── 3. Write archived copy to OUTPUT_DIR/compositions/ ────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    compositions_dir = OUTPUT_DIR / "compositions"
    compositions_dir.mkdir(parents=True, exist_ok=True)

    archived_path = compositions_dir / f"VideoComposition_{timestamp}.tsx"
    try:
        archived_path.write_text(tsx_code, encoding="utf-8")
        logger.info("[RemotionAgent] Archived composition → %s", archived_path)
    except OSError as exc:
        logger.error("[RemotionAgent] Failed to write archived TSX: %s", exc)
        return {"error": str(exc), "status": "failed"}

    # ── 4. Overwrite live Remotion composition for rendering ───────────────────
    try:
        _REMOTION_LIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _REMOTION_LIVE_PATH.write_text(tsx_code, encoding="utf-8")
        logger.info("[RemotionAgent] Live composition overwritten → %s", _REMOTION_LIVE_PATH)
    except OSError as exc:
        logger.error("[RemotionAgent] Failed to write live TSX: %s", exc)
        return {"error": str(exc), "status": "failed"}

    logger.info("[RemotionAgent] Done. remotion_project_path=%s", archived_path)
    return {
        "remotion_project_path": str(archived_path),
        "error": None,
    }
