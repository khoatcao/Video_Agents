"""
Remotion Agent — template-based video generation.

LLM generates JSON scene config only. Python fills a fixed pre-validated
TSX template using simple string replacement (no .format() — avoids JSX brace conflicts).
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

# __SCENE_DATA__ is replaced via .replace() — no .format() so JSX braces are safe
_TSX_TEMPLATE = """import { AbsoluteFill, Sequence, useCurrentFrame, interpolate, spring } from 'remotion';
import React from 'react';

const SCENE_DATA = __SCENE_DATA__;

const THEME = {
  bg: '#0a0f1e',
  surface: '#1a2235',
  card: '#1e2d45',
  text: '#f1f5f9',
  muted: '#7c8fa6',
  border: '#2a3f5f',
};

type SceneData = {
  heading: string;
  subheading?: string | null;
  bullets?: string[] | null;
  steps?: string[] | null;
  accent_color: string;
  duration_frames: number;
  scene_type: string;
};

const ease = (frame: number, delay: number, duration: number) =>
  interpolate(frame - delay, [0, duration], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const SlideUp: React.FC<{ frame: number; delay?: number; distance?: number; children: React.ReactNode }> = ({ frame, delay = 0, distance = 40, children }) => {
  const p = ease(frame, delay, 18);
  return <div style={{ opacity: p, transform: `translateY(${distance * (1 - p)}px)` }}>{children}</div>;
};

const SlideLeft: React.FC<{ frame: number; delay?: number; children: React.ReactNode }> = ({ frame, delay = 0, children }) => {
  const p = ease(frame, delay, 16);
  return <div style={{ opacity: p, transform: `translateX(${-60 * (1 - p)}px)` }}>{children}</div>;
};

const PopIn: React.FC<{ frame: number; delay?: number; children: React.ReactNode }> = ({ frame, delay = 0, children }) => {
  const s = spring({ frame: frame - delay, fps: 30, config: { damping: 14, stiffness: 180 } });
  return <div style={{ transform: `scale(${s})`, opacity: Math.min(s, 1) }}>{children}</div>;
};

const ProgressBar: React.FC<{ color: string; frame: number; total: number }> = ({ color, frame, total }) => {
  const w = interpolate(frame, [0, total * 0.85], [0, 100], { extrapolateRight: 'clamp' });
  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 6, backgroundColor: 'rgba(255,255,255,0.08)' }}>
      <div style={{ height: '100%', width: `${w}%`, backgroundColor: color, borderRadius: '0 3px 3px 0', transition: 'width 0.1s' }} />
    </div>
  );
};

const TitleScene: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const pulse = interpolate(Math.sin(frame * 0.06), [-1, 1], [0.92, 1.0]);
  return (
    <AbsoluteFill style={{ backgroundColor: THEME.bg, justifyContent: 'center', alignItems: 'center', padding: 64, flexDirection: 'column', gap: 32 }}>
      {/* Glowing orb background */}
      <div style={{ position: 'absolute', width: 500, height: 500, borderRadius: '50%', background: `radial-gradient(circle, ${scene.accent_color}22 0%, transparent 70%)`, transform: `scale(${pulse})` }} />
      <SlideUp frame={frame} delay={0}>
        <div style={{ fontSize: 100, textAlign: 'center', lineHeight: 1 }}>⚡</div>
      </SlideUp>
      <SlideUp frame={frame} delay={8}>
        <h1 style={{ color: THEME.text, fontSize: 76, fontWeight: 800, textAlign: 'center', lineHeight: 1.15, margin: 0, fontFamily: 'system-ui', letterSpacing: '-1px' }}>
          {scene.heading}
        </h1>
      </SlideUp>
      {scene.subheading && (
        <SlideUp frame={frame} delay={20}>
          <p style={{ color: THEME.muted, fontSize: 42, textAlign: 'center', margin: 0, fontFamily: 'system-ui', fontWeight: 500 }}>
            {scene.subheading}
          </p>
        </SlideUp>
      )}
      <SlideUp frame={frame} delay={28}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div style={{ height: 4, width: 60, backgroundColor: scene.accent_color, borderRadius: 2 }} />
          <div style={{ height: 4, width: 120, backgroundColor: scene.accent_color, borderRadius: 2 }} />
          <div style={{ height: 4, width: 60, backgroundColor: scene.accent_color, borderRadius: 2 }} />
        </div>
      </SlideUp>
    </AbsoluteFill>
  );
};

const BulletsScene: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const items = scene.bullets || scene.steps || [];
  const icons = ['✦', '◈', '▸', '◆'];
  return (
    <AbsoluteFill style={{ backgroundColor: THEME.bg, padding: 72, flexDirection: 'column', justifyContent: 'center', gap: 28 }}>
      <ProgressBar color={scene.accent_color} frame={frame} total={scene.duration_frames} />
      <SlideUp frame={frame} delay={0}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 8 }}>
          <div style={{ width: 8, height: 72, backgroundColor: scene.accent_color, borderRadius: 4 }} />
          <h2 style={{ color: THEME.text, fontSize: 66, fontWeight: 800, margin: 0, lineHeight: 1.15, fontFamily: 'system-ui', letterSpacing: '-0.5px' }}>
            {scene.heading}
          </h2>
        </div>
      </SlideUp>
      {items.map((item, i) => (
        <SlideLeft key={i} frame={frame} delay={18 + i * 16}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20, backgroundColor: THEME.card, borderRadius: 16, padding: '22px 28px', borderLeft: `5px solid ${scene.accent_color}` }}>
            <span style={{ color: scene.accent_color, fontSize: 36, fontWeight: 700, minWidth: 36, textAlign: 'center', fontFamily: 'system-ui' }}>
              {icons[i % icons.length]}
            </span>
            <p style={{ color: THEME.text, fontSize: 46, margin: 0, lineHeight: 1.35, fontFamily: 'system-ui', fontWeight: 500 }}>{item}</p>
          </div>
        </SlideLeft>
      ))}
    </AbsoluteFill>
  );
};

const DiagramScene: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const steps = scene.steps || scene.bullets || [];
  return (
    <AbsoluteFill style={{ backgroundColor: THEME.bg, padding: 72, flexDirection: 'column', justifyContent: 'center', gap: 24 }}>
      <ProgressBar color={scene.accent_color} frame={frame} total={scene.duration_frames} />
      <SlideUp frame={frame} delay={0}>
        <h2 style={{ color: THEME.text, fontSize: 64, fontWeight: 800, margin: '0 0 8px', fontFamily: 'system-ui', letterSpacing: '-0.5px' }}>
          {scene.heading}
        </h2>
        <div style={{ height: 4, backgroundColor: scene.accent_color, width: 100, borderRadius: 2 }} />
      </SlideUp>
      {steps.map((step, i) => {
        const entered = spring({ frame: frame - (22 + i * 20), fps: 30, config: { damping: 16, stiffness: 160 } });
        const arrowOpacity = ease(frame, 32 + i * 20, 12);
        return (
          <React.Fragment key={i}>
            <div style={{ transform: `scale(${entered})`, opacity: Math.min(entered, 1), display: 'flex', alignItems: 'center', gap: 20, backgroundColor: THEME.card, borderRadius: 18, padding: '20px 28px', border: `1px solid ${THEME.border}` }}>
              <div style={{ minWidth: 56, height: 56, borderRadius: 14, backgroundColor: scene.accent_color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ color: '#fff', fontSize: 28, fontWeight: 800, fontFamily: 'system-ui' }}>{String(i + 1).padStart(2, '0')}</span>
              </div>
              <p style={{ color: THEME.text, fontSize: 48, fontWeight: 600, margin: 0, lineHeight: 1.3, fontFamily: 'system-ui' }}>{step}</p>
            </div>
            {i < steps.length - 1 && (
              <div style={{ opacity: arrowOpacity, paddingLeft: 46, color: scene.accent_color, fontSize: 28, lineHeight: 1 }}>▼</div>
            )}
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

const FlowChartScene: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const steps = scene.steps || scene.bullets || [];
  const colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444'];
  return (
    <AbsoluteFill style={{ backgroundColor: THEME.bg, padding: 64, flexDirection: 'column', justifyContent: 'center', gap: 16 }}>
      <ProgressBar color={scene.accent_color} frame={frame} total={scene.duration_frames} />
      <SlideUp frame={frame} delay={0}>
        <h2 style={{ color: THEME.text, fontSize: 60, fontWeight: 800, margin: '0 0 16px', fontFamily: 'system-ui' }}>
          {scene.heading}
        </h2>
      </SlideUp>
      {steps.map((step, i) => {
        const c = colors[i % colors.length];
        const p = ease(frame, 16 + i * 18, 16);
        return (
          <div key={i} style={{ opacity: p, transform: `translateX(${(1 - p) * -50}px)`, display: 'flex', alignItems: 'stretch', gap: 0 }}>
            <div style={{ width: 6, backgroundColor: c, borderRadius: '4px 0 0 4px', flexShrink: 0 }} />
            <div style={{ flex: 1, backgroundColor: THEME.surface, padding: '18px 26px', borderRadius: '0 14px 14px 0', display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ width: 44, height: 44, borderRadius: '50%', backgroundColor: c + '33', border: `2px solid ${c}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <span style={{ color: c, fontSize: 22, fontWeight: 800, fontFamily: 'system-ui' }}>{i + 1}</span>
              </div>
              <p style={{ color: THEME.text, fontSize: 46, margin: 0, lineHeight: 1.3, fontFamily: 'system-ui', fontWeight: 500 }}>{step}</p>
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

const CTAScene: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const pulse = spring({ frame: Math.max(0, frame - 30), fps: 30, config: { damping: 8, stiffness: 120 } });
  const glow = interpolate(Math.sin(frame * 0.08), [-1, 1], [0.6, 1.0]);
  return (
    <AbsoluteFill style={{ backgroundColor: THEME.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 36, padding: 64 }}>
      <div style={{ position: 'absolute', width: 600, height: 600, borderRadius: '50%', background: `radial-gradient(circle, ${scene.accent_color}18 0%, transparent 65%)`, opacity: glow }} />
      <PopIn frame={frame} delay={0}>
        <div style={{ width: 130, height: 130, borderRadius: 36, backgroundColor: scene.accent_color + '22', border: `3px solid ${scene.accent_color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 72 }}>
          🚀
        </div>
      </PopIn>
      <SlideUp frame={frame} delay={18}>
        <h1 style={{ color: THEME.text, fontSize: 70, fontWeight: 800, textAlign: 'center', margin: 0, fontFamily: 'system-ui', letterSpacing: '-1px', lineHeight: 1.2 }}>
          {scene.heading}
        </h1>
      </SlideUp>
      {scene.subheading && (
        <SlideUp frame={frame} delay={28}>
          <p style={{ color: THEME.muted, fontSize: 42, textAlign: 'center', margin: 0, fontFamily: 'system-ui' }}>
            {scene.subheading}
          </p>
        </SlideUp>
      )}
      <div style={{ transform: `scale(${pulse})` }}>
        <SlideUp frame={frame} delay={38}>
          <div style={{ background: `linear-gradient(135deg, ${scene.accent_color}, ${scene.accent_color}cc)`, paddingInline: 64, paddingBlock: 26, borderRadius: 64, boxShadow: `0 0 40px ${scene.accent_color}55` }}>
            <p style={{ color: '#fff', fontSize: 46, fontWeight: 800, margin: 0, fontFamily: 'system-ui', letterSpacing: '0.5px' }}>
              Theo dõi ngay! 👆
            </p>
          </div>
        </SlideUp>
      </div>
    </AbsoluteFill>
  );
};

const SCENE_COMPONENTS: Record<string, React.FC<{ scene: SceneData }>> = {
  title: TitleScene,
  bullets: BulletsScene,
  diagram: DiagramScene,
  flow_chart: FlowChartScene,
  comparison: BulletsScene,
  cta: CTAScene,
};

export const TOTAL_FRAMES: number = SCENE_DATA.reduce(
  (sum: number, s: SceneData) => sum + s.duration_frames,
  0
);

export const VideoComposition: React.FC = () => {
  let offset = 0;
  return (
    <AbsoluteFill>
      {SCENE_DATA.map((scene, i) => {
        const from = offset;
        offset += scene.duration_frames;
        const Component = SCENE_COMPONENTS[scene.scene_type] || BulletsScene;
        return (
          <Sequence key={i} from={from} durationInFrames={scene.duration_frames}>
            <Component scene={scene} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
"""


def _extract_json_array(text: str) -> list[Any]:
    """Extract first JSON array from LLM response, handling wrapped objects."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for val in result.values():
                if isinstance(val, list) and val:
                    return val
    except json.JSONDecodeError:
        pass

    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            result = json.loads(text[start:end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No JSON array found in LLM response:\n{text[:500]}")


_MIN_TOTAL_FRAMES = 1350   # 45 s at 30 fps
_MAX_TOTAL_FRAMES = 1800   # 60 s at 30 fps
_MIN_SCENE_FRAMES = 240    # 8 s minimum per scene


def _validate_scenes(scenes: list[Any]) -> list[dict]:
    """Validate, normalise, and enforce 45-60 s total duration."""
    valid_types = {"title", "bullets", "diagram", "flow_chart", "comparison", "cta"}
    valid_colors = {"#3b82f6", "#10b981", "#f59e0b", "#ef4444"}
    result = []
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        result.append({
            "heading":         str(scene.get("heading", f"Scene {i + 1}")),
            "subheading":      scene.get("subheading") or None,
            "bullets":         scene.get("bullets") or None,
            "steps":           scene.get("steps") or None,
            "accent_color":    scene.get("accent_color", "#3b82f6") if scene.get("accent_color") in valid_colors else "#3b82f6",
            "duration_frames": max(_MIN_SCENE_FRAMES, int(scene.get("duration_frames", _MIN_SCENE_FRAMES))),
            "scene_type":      scene.get("scene_type", "bullets") if scene.get("scene_type") in valid_types else "bullets",
        })

    if not result:
        return result

    # Scale up proportionally if total is below 45 s
    total = sum(s["duration_frames"] for s in result)
    if total < _MIN_TOTAL_FRAMES:
        scale = _MIN_TOTAL_FRAMES / total
        for s in result:
            s["duration_frames"] = int(s["duration_frames"] * scale)
        logger.info("[RemotionAgent] Scaled frames %.0f→%d to meet 45 s minimum.", total, sum(s["duration_frames"] for s in result))

    # Cap at 60 s
    total = sum(s["duration_frames"] for s in result)
    if total > _MAX_TOTAL_FRAMES:
        scale = _MAX_TOTAL_FRAMES / total
        for s in result:
            s["duration_frames"] = int(s["duration_frames"] * scale)

    return result


def _build_tsx(scenes: list[dict]) -> str:
    """Fill the TSX template — simple replace, no .format() to avoid JSX brace conflicts."""
    scene_json = json.dumps(scenes, ensure_ascii=False, indent=2)
    return _TSX_TEMPLATE.replace("__SCENE_DATA__", scene_json)


def remotion_node(state: PipelineState) -> dict:
    """
    LangGraph node: generate VideoComposition.tsx from scene_plan.
    LLM generates JSON scene config → Python fills TSX template.
    """
    scene_plan = state.get("scene_plan", [])

    if not scene_plan:
        return {"error": "scene_plan is empty.", "status": "failed"}

    llm = ChatOllama(
        model=MODEL_CODE,
        base_url=OLLAMA_BASE_URL,
        temperature=0.4,
    )

    human_prompt = (
        "Convert this scene plan into a JSON array of scene config objects.\n\n"
        f"SCENE PLAN:\n{json.dumps(scene_plan, ensure_ascii=False, indent=2)}\n\n"
        "Return ONLY a valid JSON array. No explanation, no markdown."
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

    logger.info("[RemotionAgent] Raw response (%d chars): %s", len(raw), raw[:300])

    try:
        scenes_raw = _extract_json_array(raw)
    except ValueError as exc:
        logger.error("[RemotionAgent] JSON parse failed: %s", exc)
        return {"error": str(exc), "status": "failed"}

    scenes = _validate_scenes(scenes_raw)
    if not scenes:
        return {"error": "LLM returned no valid scenes.", "status": "failed"}

    scenes[0]["scene_type"] = "title"
    scenes[-1]["scene_type"] = "cta"

    tsx = _build_tsx(scenes)
    total_frames = sum(s["duration_frames"] for s in scenes)
    logger.info("[RemotionAgent] %d scenes, %d total frames.", len(scenes), total_frames)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = OUTPUT_DIR / "compositions"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"VideoComposition_{timestamp}.tsx"
    archive_path.write_text(tsx, encoding="utf-8")
    logger.info("[RemotionAgent] Archived → %s", archive_path)

    _LIVE_COMPOSITION.parent.mkdir(parents=True, exist_ok=True)
    _LIVE_COMPOSITION.write_text(tsx, encoding="utf-8")
    logger.info("[RemotionAgent] Live composition written → %s", _LIVE_COMPOSITION)

    return {"remotion_project_path": str(archive_path), "error": None}
