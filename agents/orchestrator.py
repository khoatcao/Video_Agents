"""
Orchestrator helpers for the LangGraph video-generation pipeline.

These are NOT LangGraph nodes themselves.  They are used as:
  - Conditional edge functions  (should_retry)
  - Regular node functions       (handle_error, fail_node)
"""

from __future__ import annotations

import logging

from state.pipeline_state import PipelineState

logger = logging.getLogger(__name__)


def should_retry(state: PipelineState) -> str:
    """
    Conditional edge function: route based on error state.

    Returns:
        "retry"    — there is an error and retry_count < 2 (max 2 retries)
        "fail"     — there is an error but retry limit exhausted
        "continue" — no error, proceed to the next node
    """
    if state.get("error"):
        retry_count = state.get("retry_count", 0)
        if retry_count < 2:
            logger.warning(
                "[Orchestrator] Error detected (attempt %d/2): %s — retrying.",
                retry_count + 1,
                state["error"],
            )
            return "retry"
        else:
            logger.error(
                "[Orchestrator] Retry limit reached after %d attempts. Error: %s",
                retry_count,
                state["error"],
            )
            return "fail"
    return "continue"


def handle_error(state: PipelineState) -> dict:
    """
    Node function: increment retry_count and clear the error flag so the
    pipeline can attempt the failed node again.
    """
    new_count = state.get("retry_count", 0) + 1
    logger.info("[Orchestrator] Incrementing retry_count to %d, clearing error.", new_count)
    return {"retry_count": new_count, "error": None}


def fail_node(state: PipelineState) -> dict:
    """
    Terminal failure node: mark the pipeline as failed and log the reason.
    """
    logger.error(
        "[Orchestrator] Pipeline failed permanently. Error: %s  retry_count=%d",
        state.get("error", "unknown"),
        state.get("retry_count", 0),
    )
    return {"status": "failed"}
