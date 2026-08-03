"""
Remotion Agent for the LangGraph video-generation pipeline.

Takes scene_plan from state, calls qwen2.5:7b to generate a self-contained
VideoComposition.tsx, validates it with tsc, repairs up to 3 times on error,
then writes it to the live Remotion compositions folder.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config.prompts.remotion_agent import REMOTION_AGENT_SYSTEM_PROMPT
from config.settings import MODEL_CODE, OLLAMA_BASE_URL, OUTPUT_DIR
from state.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REMOTION_ROOT = _PROJECT_ROOT / "remotion"
_LIVE_COMPOSITION = _REMOTION_ROOT / "src" / "compositions" / "VideoComposition.tsx"
_MAX_REPAIR_ATTEMPTS = 2
_TSC_TIMEOUT = 90


# ── TSX extraction ────────────────────────────────────────────────────────────

def _extract_tsx(text: str) -> str:
    """Extract TypeScript/TSX code from LLM response."""
    if not text:
        raise ValueError("LLM returned an empty response.")

    for pattern in [
        r"```tsx\s*([\s\S]*?)```",
        r"```typescript\s*([\s\S]*?)```",
        r"```ts\s*([\s\S]*?)```",
        r"```\s*([\s\S]*?)```",
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            code = match.group(1).strip()
            if code:
                return code

    stripped = text.strip()
    stripped = re.sub(r"^```(?:tsx|typescript|ts)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped).strip()

    if any(stripped.startswith(p) for p in ("import ", "export ", "//", "const ")):
        return stripped

    raise ValueError(f"Could not extract TSX from LLM response:\n{stripped[:500]}")


# ── Validation ────────────────────────────────────────────────────────────────

def _basic_validate(tsx: str) -> tuple[bool, str]:
    """Fast pre-checks before running tsc."""
    checks = [
        (bool(tsx.strip()),                              "TSX is empty."),
        ("VideoComposition" in tsx,                      "Missing VideoComposition."),
        ("export const VideoComposition" in tsx,         "Missing 'export const VideoComposition'."),
        ("export" in tsx,                                "No export found."),
        ("```" not in tsx,                               "TSX still contains markdown fences."),
    ]
    forbidden = ["./components", "../components", "./utils", "../utils",
                 "./scene", "../scene", "./helpers", "../helpers"]
    for imp in forbidden:
        checks.append((imp not in tsx, f"Forbidden local import: {imp}"))

    for ok, msg in checks:
        if not ok:
            return False, msg
    return True, ""


def _tsc_validate(tsx: str) -> tuple[bool, str]:
    """Write TSX to live path, run tsc --noEmit, restore original."""
    ok, msg = _basic_validate(tsx)
    if not ok:
        return False, msg

    if not _REMOTION_ROOT.exists() or not (_REMOTION_ROOT / "package.json").exists():
        return False, f"Remotion project not found at {_REMOTION_ROOT}"

    _LIVE_COMPOSITION.parent.mkdir(parents=True, exist_ok=True)
    backup = _LIVE_COMPOSITION.with_suffix(".tsx.__backup__")
    had_original = _LIVE_COMPOSITION.exists()

    try:
        if had_original:
            backup.write_bytes(_LIVE_COMPOSITION.read_bytes())

        _LIVE_COMPOSITION.write_text(tsx, encoding="utf-8")

        result = subprocess.run(
            ["npx", "tsc", "--noEmit", "--pretty", "false"],
            cwd=_REMOTION_ROOT,
            capture_output=True,
            text=True,
            timeout=_TSC_TIMEOUT,
        )

        if result.returncode == 0:
            return True, ""

        error = result.stdout.strip() or result.stderr.strip() or "tsc failed."
        return False, error

    except FileNotFoundError:
        return False, "npx/Node.js not found. Run: cd remotion && npm install"
    except subprocess.TimeoutExpired:
        return False, f"tsc timed out after {_TSC_TIMEOUT}s."
    except Exception as exc:
        return False, f"Validation error: {exc}"
    finally:
        try:
            if had_original and backup.exists():
                _LIVE_COMPOSITION.write_bytes(backup.read_bytes())
            elif not had_original:
                _LIVE_COMPOSITION.unlink(missing_ok=True)
        except Exception as e:
            logger.error("[RemotionAgent] Failed to restore backup: %s", e)
        backup.unlink(missing_ok=True)


# ── LLM helpers ───────────────────────────────────────────────────────────────

def _invoke_llm(llm: ChatOllama, messages: list) -> str:
    response = llm.invoke(messages)
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "\n".join(str(item.get("text", item)) if isinstance(item, dict) else str(item)
                         for item in content)
    return str(content)


def _generation_prompt(scene_plan: list) -> str:
    scene_json = json.dumps(scene_plan, ensure_ascii=False, indent=2)
    return (
        "Generate a complete, self-contained Remotion VideoComposition.tsx "
        "for the scene plan below.\n\n"
        "SCENE PLAN:\n"
        f"{scene_json}\n\n"
        "REQUIREMENTS:\n"
        "- Export: export const VideoComposition = () => { ... }\n"
        "- Only import from 'remotion' and 'react' — no local file imports\n"
        "- Use AbsoluteFill, Sequence, useCurrentFrame, interpolate, spring\n"
        "- Video: 1080x1920 (9:16), 30fps, dark background (#0f172a)\n"
        "- ByteByteGo style: bold text, colored boxes, smooth animations\n"
        "- All text in Vietnamese\n"
        "Return ONLY the TSX code inside a ```tsx block."
    )


def _repair_prompt(tsx: str, error: str) -> str:
    return (
        "The Remotion composition failed TypeScript validation. Fix ALL errors.\n\n"
        f"COMPILER ERROR:\n{error}\n\n"
        f"CURRENT TSX:\n```tsx\n{tsx}\n```\n\n"
        "Return ONLY the corrected TSX inside a ```tsx block."
    )


# ── Main node ─────────────────────────────────────────────────────────────────

def remotion_node(state: PipelineState) -> dict:
    """
    LangGraph node: generate VideoComposition.tsx from scene_plan.

    Reads:  state["scene_plan"], state["slot"]
    Writes: remotion_project_path  — or — error, status
    """
    scene_plan = state.get("scene_plan", [])
    slot = state.get("slot", "morning")

    if not scene_plan:
        return {"error": "scene_plan is empty.", "status": "failed"}

    llm = ChatOllama(
        model=MODEL_CODE,
        base_url=OLLAMA_BASE_URL,
        temperature=0.4,
    )

    logger.info("[RemotionAgent] Invoking %s for %d scenes …", MODEL_CODE, len(scene_plan))

    messages = [
        SystemMessage(content=REMOTION_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=_generation_prompt(scene_plan)),
    ]

    try:
        raw = _invoke_llm(llm, messages)
    except Exception as exc:
        return {"error": f"LLM call failed: {exc}", "status": "failed"}

    try:
        tsx = _extract_tsx(raw)
    except ValueError as exc:
        return {"error": str(exc), "status": "failed"}

    # Validate and repair loop
    for attempt in range(_MAX_REPAIR_ATTEMPTS + 1):
        valid, error = _tsc_validate(tsx)
        if valid:
            break

        if attempt == _MAX_REPAIR_ATTEMPTS:
            logger.warning(
                "[RemotionAgent] tsc still failing after %d repairs — using last version anyway.",
                _MAX_REPAIR_ATTEMPTS,
            )
            break

        logger.warning("[RemotionAgent] tsc error (attempt %d): %s", attempt + 1, error[:200])
        try:
            raw = _invoke_llm(llm, [
                SystemMessage(content=REMOTION_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=_repair_prompt(tsx, error)),
            ])
            tsx = _extract_tsx(raw)
        except Exception as exc:
            logger.warning("[RemotionAgent] Repair attempt %d failed: %s", attempt + 1, exc)
            break

    # Archive copy
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = OUTPUT_DIR / "compositions"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"VideoComposition_{timestamp}.tsx"
    archive_path.write_text(tsx, encoding="utf-8")
    logger.info("[RemotionAgent] Archived composition → %s", archive_path)

    # Write live composition for Remotion to render
    _LIVE_COMPOSITION.parent.mkdir(parents=True, exist_ok=True)
    _LIVE_COMPOSITION.write_text(tsx, encoding="utf-8")
    logger.info("[RemotionAgent] Live composition overwritten → %s", _LIVE_COMPOSITION)

    logger.info("[RemotionAgent] Done. remotion_project_path=%s", archive_path)
    return {"remotion_project_path": str(archive_path), "error": None}
