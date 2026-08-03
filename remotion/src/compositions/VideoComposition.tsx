import { AbsoluteFill, Sequence, useCurrentFrame, interpolate, spring } from 'remotion';
import React from 'react';

const SCENE_DATA = [
  {
    heading: "Video sẽ được tạo tự động",
    subheading: "Chạy pipeline để tạo nội dung",
    bullets: null,
    steps: null,
    accent_color: "#3b82f6",
    duration_frames: 90,
    scene_type: "title",
  },
  {
    heading: "Theo dõi kênh nhé!",
    subheading: null,
    bullets: null,
    steps: null,
    accent_color: "#10b981",
    duration_frames: 90,
    scene_type: "cta",
  },
];

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
      <div style={{ height: '100%', width: `${w}%`, backgroundColor: color, borderRadius: '0 3px 3px 0' }} />
    </div>
  );
};

const TitleScene: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const pulse = interpolate(Math.sin(frame * 0.06), [-1, 1], [0.92, 1.0]);
  return (
    <AbsoluteFill style={{ backgroundColor: THEME.bg, justifyContent: 'center', alignItems: 'center', padding: 64, flexDirection: 'column', gap: 32 }}>
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
