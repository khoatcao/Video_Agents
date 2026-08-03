"""
Remotion Agent for the LangGraph video-generation pipeline.

Flow:

    scene_plan
        ↓
    LLM generates TSX
        ↓
    extract TSX
        ↓
    basic validation
        ↓
    TypeScript validation
        ↓
    if invalid
        ↓
    LLM receives compiler error
        ↓
    generates corrected TSX
        ↓
    validate again
        ↓
    archive + write live composition

Important:
    The generated VideoComposition.tsx is intentionally self-contained.
    The LLM must NOT invent local imports such as "./components".
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


# ============================================================================
# Paths
# ============================================================================

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_REMOTION_ROOT = _PROJECT_ROOT / "remotion"

_REMOTION_LIVE_PATH = (
    _REMOTION_ROOT
    / "src"
    / "compositions"
    / "VideoComposition.tsx"
)


# ============================================================================
# Configuration
# ============================================================================

_MAX_REPAIR_ATTEMPTS = 3

_VALIDATION_TIMEOUT_SECONDS = 90


# ============================================================================
# TSX extraction
# ============================================================================

def _extract_tsx(text: str) -> str:
    """
    Extract TypeScript/TSX from an LLM response.

    Supports:

        ```tsx
        ...
        ```

        ```typescript
        ...
        ```

        ```ts
        ...
        ```

        ```
        ...
        ```

    Also supports raw TSX responses.
    """

    if not text:
        raise ValueError("LLM returned an empty response.")

    patterns = [
        r"```tsx\s*([\s\S]*?)```",
        r"```typescript\s*([\s\S]*?)```",
        r"```ts\s*([\s\S]*?)```",
        r"```\s*([\s\S]*?)```",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            code = match.group(1).strip()

            if code:
                return code

    stripped = text.strip()

    # Remove accidental leading/trailing markdown fences.
    stripped = re.sub(
        r"^```(?:tsx|typescript|ts)?\s*",
        "",
        stripped,
        flags=re.IGNORECASE,
    )

    stripped = re.sub(
        r"\s*```$",
        "",
        stripped,
    )

    stripped = stripped.strip()

    if (
        stripped.startswith("import ")
        or stripped.startswith("export ")
        or stripped.startswith("//")
        or stripped.startswith("const ")
    ):
        return stripped

    raise ValueError(
        "Could not extract TSX from LLM response.\n"
        f"Response starts with:\n{stripped[:1000]}"
    )


# ============================================================================
# Basic validation
# ============================================================================

def _basic_validate_tsx(
    tsx_code: str,
) -> tuple[bool, str]:
    """
    Perform cheap validation before invoking TypeScript.
    """

    if not tsx_code.strip():
        return False, "Generated TSX is empty."

    if "VideoComposition" not in tsx_code:
        return (
            False,
            "Generated TSX does not contain VideoComposition.",
        )

    if "export" not in tsx_code:
        return (
            False,
            "Generated TSX does not contain an export.",
        )

    if "```" in tsx_code:
        return (
            False,
            "Generated TSX still contains Markdown code fences.",
        )

    if "export const VideoComposition" not in tsx_code:
        return (
            False,
            "Generated TSX must contain "
            "'export const VideoComposition'.",
        )

    if "Composition" not in tsx_code:
        return (
            False,
            "Generated TSX does not contain a Remotion Composition.",
        )

    if "<Sequence" in tsx_code:
        if "Sequence" not in tsx_code:
            return (
                False,
                "Sequence is used but not imported.",
            )

    # The generated file must not depend on AI-invented local files.
    forbidden_local_imports = [
        "./components",
        "../components",
        "./utils",
        "../utils",
        "./scene",
        "../scene",
        "./helpers",
        "../helpers",
    ]

    for forbidden in forbidden_local_imports:
        if forbidden in tsx_code:
            return (
                False,
                f"Generated TSX contains unsupported local import: "
                f"{forbidden}. "
                "The composition must be self-contained.",
            )

    return True, ""


# ============================================================================
# TypeScript validation
# ============================================================================

def _validate_with_remotion(
    tsx_code: str,
) -> tuple[bool, str]:
    """
    Validate the generated composition against the real Remotion project.

    The generated file is temporarily written to the actual composition
    path, TypeScript is executed, and the original file is restored.

    This is important because validating a fake
    VideoComposition.__validation__.tsx file caused false errors such as:

        Cannot find module './components'
        Cannot find name 'Sequence'
        Cannot find name 'useVideoConfig'

    We want validation against the actual project structure.
    """

    valid, error = _basic_validate_tsx(tsx_code)

    if not valid:
        return False, error

    if not _REMOTION_ROOT.exists():
        return (
            False,
            f"Remotion project does not exist: {_REMOTION_ROOT}",
        )

    if not (_REMOTION_ROOT / "package.json").exists():
        return (
            False,
            f"Remotion package.json not found in {_REMOTION_ROOT}",
        )

    _REMOTION_LIVE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------------------
    # Backup existing composition
    # ------------------------------------------------------------------

    backup_path = (
        _REMOTION_LIVE_PATH.with_suffix(
            ".tsx.__agent_backup__"
        )
    )

    had_original = _REMOTION_LIVE_PATH.exists()

    try:

        if had_original:
            backup_path.write_bytes(
                _REMOTION_LIVE_PATH.read_bytes()
            )

        # --------------------------------------------------------------
        # Write candidate into the actual Remotion source tree.
        # --------------------------------------------------------------

        _REMOTION_LIVE_PATH.write_text(
            tsx_code,
            encoding="utf-8",
        )

        # --------------------------------------------------------------
        # Run TypeScript compiler.
        # --------------------------------------------------------------

        result = subprocess.run(
            [
                "npx",
                "tsc",
                "--noEmit",
                "--pretty",
                "false",
            ],
            cwd=_REMOTION_ROOT,
            capture_output=True,
            text=True,
            timeout=_VALIDATION_TIMEOUT_SECONDS,
        )

        if result.returncode == 0:
            return True, ""

        compiler_error = (
            result.stdout.strip()
            or result.stderr.strip()
            or "TypeScript validation failed."
        )

        return False, compiler_error

    except FileNotFoundError:
        return (
            False,
            "Node.js/npm/npx was not found. "
            "Make sure Node.js is installed and available in PATH.",
        )

    except subprocess.TimeoutExpired:
        return (
            False,
            "TypeScript validation timed out after "
            f"{_VALIDATION_TIMEOUT_SECONDS} seconds.",
        )

    except Exception as exc:
        return (
            False,
            f"Validation failed unexpectedly: {exc}",
        )

    finally:

        # --------------------------------------------------------------
        # Restore original composition.
        # --------------------------------------------------------------

        try:

            if had_original and backup_path.exists():

                _REMOTION_LIVE_PATH.write_bytes(
                    backup_path.read_bytes()
                )

            elif not had_original:

                _REMOTION_LIVE_PATH.unlink(
                    missing_ok=True
                )

        except Exception as restore_exc:

            logger.error(
                "[RemotionAgent] Failed to restore "
                "original VideoComposition.tsx: %s",
                restore_exc,
            )

        finally:

            backup_path.unlink(
                missing_ok=True
            )


# ============================================================================
# LLM invocation
# ============================================================================

def _invoke_llm(
    llm: ChatOllama,
    messages: list,
) -> str:
    """
    Invoke Ollama and normalize its response to a string.
    """

    response = llm.invoke(messages)

    content = getattr(
        response,
        "content",
        response,
    )

    if isinstance(content, list):

        parts: list[str] = []

        for item in content:

            if isinstance(item, dict):
                parts.append(
                    str(item.get("text", ""))
                )
            else:
                parts.append(
                    str(item)
                )

        return "\n".join(parts)

    return str(content)


def _build_repair_prompt(
    tsx_code: str,
    compiler_error: str,
) -> str:
    return f"""
The Remotion composition you generated failed TypeScript validation.

You MUST repair it.

============================================================
COMPILER ERROR
============================================================

{compiler_error}

============================================================
CURRENT TSX
============================================================

```tsx
{tsx_code}





### 2. Add `_build_generation_prompt()`

Put this **immediately after `_build_repair_prompt()`**:

```python
# ============================================================================
# Initial generation prompt
# ============================================================================

def _build_generation_prompt(
    scene_plan: list,
) -> str:
    scene_json = json.dumps(
        scene_plan,
        ensure_ascii=False,
        indent=2,
    )

    return f"""
    Generate the complete Remotion VideoComposition.tsx for the scene plan below.

    SCENE PLAN:
    {scene_json}

    ============================================================
STRICT REQUIREMENTS
============================================================