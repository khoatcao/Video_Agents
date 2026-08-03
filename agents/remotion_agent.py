"""
Remotion Agent — template-based video generation.

LLM generates JSON scene config only. Python fills a fixed pre-validated
TSX template. No TypeScript generation by LLM = no syntax errors.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config.prompts.remotion_agent import REMOTION_AGENT_SYSTEM_PROMPT
from config.settings import MODEL_CODE, OLLAMA_BASE_URL, OUTPUT_DIR
from state.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LIVE_COMPOSITION = (
    _PROJECT_ROOT / "remotion" / "src" / "compositions" / "VideoComposition.tsx"
)

# Fixed, pre-validated TSX template — LLM never touches TypeScript
_TSX_TEMPLATE = '''import {{ AbsoluteFill, Sequence, useCurrentFrame, interpolate, spring }} from 'remotion';
import React from 'react';

const SCENE_DATA = {scene_data_json};

const THEME = {{
  bg: '#0f172a',
  surface: '#1e293b',
  text: '#f8fafc',
  muted: '#94a3b8',
}};

const FadeIn: React.FC<{{ frame: number; delay?: number; children: React.ReactNode }}> = ({{ frame, delay = 0, children }}) => {{
  const opacity = interpolate(frame - delay, [0, 15], [0, 1], {{ extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }});
  const y = interpolate(frame - delay, [0, 15], [30, 0], {{ extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }});
  return <div style={{{{ opacity, transform: `translateY(${{y}}px)` }}}}>{children}</div>;
}};

type SceneData = {{
  heading: string;
  subheading?: string | null;
  bullets?: string[] | null;
  steps?: string[] | null;
  accent_color: string;
  duration_frames: number;
  scene_type: string;
}};

const TitleScene: React.FC<{{ scene: SceneData }}> = ({{ scene }}) => {{
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{{{ backgroundColor: THEME.bg, justifyContent: 'center', alignItems: 'center', padding: 60, flexDirection: 'column', gap: 24 }}}}>
      <FadeIn frame={{frame}}>
        <h1 style={{{{ color: THEME.text, fontSize: 80, fontWeight: 700, textAlign: 'center', lineHeight: 1.2, margin: 0, fontFamily: 'system-ui' }}}}>{scene.heading}</h1>
      </FadeIn>
      {{scene.subheading && (
        <FadeIn frame={{frame}} delay={{15}}>
          <p style={{{{ color: THEME.muted, fontSize: 44, textAlign: 'center', margin: 0, fontFamily: 'system-ui' }}}}>{scene.subheading}</p>
        </FadeIn>
      )}}
      <FadeIn frame={{frame}} delay={{25}}>
        <div style={{{{ height: 6, backgroundColor: scene.accent_color, width: 200, borderRadius: 3 }}}} />
      </FadeIn>
    </AbsoluteFill>
  );
}};

const BulletsScene: React.FC<{{ scene: SceneData }}> = ({{ scene }}) => {{
  const frame = useCurrentFrame();
  const items = scene.bullets || scene.steps || [];
  return (
    <AbsoluteFill style={{{{ backgroundColor: THEME.bg, padding: 80, flexDirection: 'column', justifyContent: 'center', gap: 36 }}}}>
      <FadeIn frame={{frame}}>
        <h2 style={{{{ color: THEME.text, fontSize: 68, fontWeight: 700, margin: 0, lineHeight: 1.2, fontFamily: 'system-ui' }}}}>{scene.heading}</h2>
        <div style={{{{ height: 4, backgroundColor: scene.accent_color, width: 120, marginTop: 16, borderRadius: 2 }}}} />
      </FadeIn>
      {{items.map((item, i) => (
        <FadeIn key={{i}} frame={{frame}} delay={{15 + i * 12}}>
          <div style={{{{ display: 'flex', alignItems: 'center', gap: 24 }}}}>
            <div style={{{{ width: 14, height: 14, borderRadius: '50%', backgroundColor: scene.accent_color, flexShrink: 0 }}}} />
            <p style={{{{ color: THEME.text, fontSize: 48, margin: 0, lineHeight: 1.4, fontFamily: 'system-ui' }}}}>{item}</p>
          </div>
        </FadeIn>
      ))}}
    </AbsoluteFill>
  );
}};

const DiagramScene: React.FC<{{ scene: SceneData }}> = ({{ scene }}) => {{
  const frame = useCurrentFrame();
  const steps = scene.steps || scene.bullets || [];
  return (
    <AbsoluteFill style={{{{ backgroundColor: THEME.bg, padding: 80, flexDirection: 'column', justifyContent: 'center', gap: 28 }}}}>
      <FadeIn frame={{frame}}>
        <h2 style={{{{ color: THEME.text, fontSize: 68, fontWeight: 700, margin: 0, fontFamily: 'system-ui' }}}}>{scene.heading}</h2>
        <div style={{{{ height: 4, backgroundColor: scene.accent_color, width: 120, marginTop: 16, borderRadius: 2 }}}} />
      </FadeIn>
      {{steps.map((step, i) => {{
        const scale = spring({{ frame: frame - (20 + i * 18), fps: 30, config: {{ damping: 12 }} }});
        return (
          <div key={{i}} style={{{{ transform: `scale(${{scale}})`, backgroundColor: THEME.surface, borderLeft: `6px solid ${{scene.accent_color}}`, padding: '24px 36px', borderRadius: 12 }}}}>
            <span style={{{{ color: THEME.muted, fontSize: 30, fontWeight: 600, fontFamily: 'system-ui' }}}}>0{{i + 1}}</span>
            <p style={{{{ color: THEME.text, fontSize: 50, fontWeight: 700, margin: '8px 0 0', fontFamily: 'system-ui' }}}}>{step}</p>
          </div>
        );
      }}))}}
    </AbsoluteFill>
  );
}};

const CTAScene: React.FC<{{ scene: SceneData }}> = ({{ scene }}) => {{
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{{{ backgroundColor: THEME.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 32, padding: 60 }}}}>
      <FadeIn frame={{frame}}>
        <div style={{{{ fontSize: 120, textAlign: 'center' }}}}>🤖</div>
      </FadeIn>
      <FadeIn frame={{frame}} delay={{15}}>
        <h1 style={{{{ color: THEME.text, fontSize: 72, fontWeight: 700, textAlign: 'center', margin: 0, fontFamily: 'system-ui' }}}}>{scene.heading}</h1>
      </FadeIn>
      {{scene.subheading && (
        <FadeIn frame={{frame}} delay={{28}}>
          <p style={{{{ color: THEME.muted, fontSize: 44, textAlign: 'center', margin: 0, fontFamily: 'system-ui' }}}}>{scene.subheading}</p>
        </FadeIn>
      )}}
      <FadeIn frame={{frame}} delay={{40}}>
        <div style={{{{ backgroundColor: scene.accent_color, paddingInline: 60, paddingBlock: 24, borderRadius: 60 }}}}>
          <p style={{{{ color: '#fff', fontSize: 44, fontWeight: 700, margin: 0, fontFamily: 'system-ui' }}}}>Theo dõi ngay! 👆</p>
        </div>
      </FadeIn>
    </AbsoluteFill>
  );
}};

const SCENE_COMPONENTS: Record<string, React.FC<{{ scene: SceneData }}>> = {{
  title: TitleScene,
  bullets: BulletsScene,
  diagram: DiagramScene,
  flow_chart: DiagramScene,
  comparison: BulletsScene,
  cta: CTAScene,
}};

export const VideoComposition: React.FC = () => {{
  let offset = 0;
  return (
    <AbsoluteFill>
      {{SCENE_DATA.map((scene, i) => {{
        const from = offset;
        offset += scene.duration_frames;
        const Component = SCENE_COMPONENTS[scene.scene_type] || BulletsScene;
        return (
          <Sequence key={{i}} from={{from}} durationInFrames={{scene.duration_frames}}>
            <Component scene={{scene}} />
          </Sequence>
        );
      }})}}
    </AbsoluteFill>
  );
}};
'''


def _extract_json_array(text: str) -> list[Any]:
    """Extract first JSON array from LLM response, handling wrapped objects."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()

    # Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        # Handle {"scenes": [...]} or {"data": [...]} wrapping
        if isinstance(result, dict):
            for val in result.values():
                if isinstance(val, list) and val:
                    return val
    except json.JSONDecodeError:
        pass

    # Find bare array in text
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            result = json.loads(text[start:end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No JSON array found in LLM response:\n{text[:500]}")


def _validate_scenes(scenes: list[Any]) -> list[dict]:
    """Validate and normalise scene objects, filling defaults where needed."""
    valid_types = {"title", "bullets", "diagram", "flow_chart", "comparison", "cta"}
    valid_colors = {"#3b82f6", "#10b981", "#f59e0b", "#ef4444"}
    result = []
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        result.append({
            "heading":        str(scene.get("heading", f"Scene {i + 1}")),
            "subheading":     scene.get("subheading") or None,
            "bullets":        scene.get("bullets") or None,
            "steps":          scene.get("steps") or None,
            "accent_color":   scene.get("accent_color", "#3b82f6") if scene.get("accent_color") in valid_colors else "#3b82f6",
            "duration_frames": max(60, int(scene.get("duration_frames", 90))),
            "scene_type":     scene.get("scene_type", "bullets") if scene.get("scene_type") in valid_types else "bullets",
        })
    return result


def _build_tsx(scenes: list[dict]) -> str:
    """Fill the TSX template with validated scene data."""
    scene_json = json.dumps(scenes, ensure_ascii=False, indent=2)
    return _TSX_TEMPLATE.format(scene_data_json=scene_json)


def remotion_node(state: PipelineState) -> dict:
    """
    LangGraph node: generate VideoComposition.tsx from scene_plan.

    LLM generates JSON scene config → Python fills TSX template.
    No TypeScript written by LLM = no syntax errors.

    Reads:  state["scene_plan"]
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
        # No format="json" — Ollama JSON mode forces an object {}, not array []
    )

    human_prompt = (
        "Convert this scene plan into a JSON array of scene config objects.\n\n"
        f"SCENE PLAN:\n{json.dumps(scene_plan, ensure_ascii=False, indent=2)}\n\n"
        "Return ONLY a valid JSON array."
    )

    logger.info("[RemotionAgent] Invoking %s for %d scenes …", MODEL_CODE, len(scene_plan))
    try:
        response = llm.invoke([
            SystemMessage(content=REMOTION_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=human_prompt),
        ])
        raw = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        return {"error": f"LLM call failed: {exc}", "status": "failed"}

    logger.info("[RemotionAgent] Raw LLM response (%d chars): %s", len(raw), raw[:300])
    try:
        scenes_raw = _extract_json_array(raw)
    except ValueError as exc:
        logger.error("[RemotionAgent] JSON parse failed: %s", exc)
        return {"error": str(exc), "status": "failed"}

    scenes = _validate_scenes(scenes_raw)
    if not scenes:
        return {"error": "LLM returned no valid scenes.", "status": "failed"}

    # Ensure first=title, last=cta
    scenes[0]["scene_type"] = "title"
    scenes[-1]["scene_type"] = "cta"

    tsx = _build_tsx(scenes)
    total_frames = sum(s["duration_frames"] for s in scenes)
    logger.info("[RemotionAgent] Generated %d scenes, %d total frames.", len(scenes), total_frames)

    # Archive copy
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = OUTPUT_DIR / "compositions"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"VideoComposition_{timestamp}.tsx"
    archive_path.write_text(tsx, encoding="utf-8")
    logger.info("[RemotionAgent] Archived → %s", archive_path)

    # Write live composition
    _LIVE_COMPOSITION.parent.mkdir(parents=True, exist_ok=True)
    _LIVE_COMPOSITION.write_text(tsx, encoding="utf-8")
    logger.info("[RemotionAgent] Live composition written → %s", _LIVE_COMPOSITION)

    return {"remotion_project_path": str(archive_path), "error": None}
