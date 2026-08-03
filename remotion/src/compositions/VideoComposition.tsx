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
  bg: '#0f172a',
  surface: '#1e293b',
  text: '#f8fafc',
  muted: '#94a3b8',
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

const FadeIn: React.FC<{ frame: number; delay?: number; children: React.ReactNode }> = ({ frame, delay = 0, children }) => {
  const opacity = interpolate(frame - delay, [0, 15], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const y = interpolate(frame - delay, [0, 15], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return <div style={{ opacity, transform: `translateY(${y}px)` }}>{children}</div>;
};

const TitleScene: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: THEME.bg, justifyContent: 'center', alignItems: 'center', padding: 60, flexDirection: 'column', gap: 24 }}>
      <FadeIn frame={frame}>
        <h1 style={{ color: THEME.text, fontSize: 80, fontWeight: 700, textAlign: 'center', lineHeight: 1.2, margin: 0, fontFamily: 'system-ui' }}>
          {scene.heading}
        </h1>
      </FadeIn>
      {scene.subheading && (
        <FadeIn frame={frame} delay={15}>
          <p style={{ color: THEME.muted, fontSize: 44, textAlign: 'center', margin: 0, fontFamily: 'system-ui' }}>
            {scene.subheading}
          </p>
        </FadeIn>
      )}
      <FadeIn frame={frame} delay={25}>
        <div style={{ height: 6, backgroundColor: scene.accent_color, width: 200, borderRadius: 3 }} />
      </FadeIn>
    </AbsoluteFill>
  );
};

const BulletsScene: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const items = scene.bullets || scene.steps || [];
  return (
    <AbsoluteFill style={{ backgroundColor: THEME.bg, padding: 80, flexDirection: 'column', justifyContent: 'center', gap: 36 }}>
      <FadeIn frame={frame}>
        <h2 style={{ color: THEME.text, fontSize: 68, fontWeight: 700, margin: 0, lineHeight: 1.2, fontFamily: 'system-ui' }}>
          {scene.heading}
        </h2>
        <div style={{ height: 4, backgroundColor: scene.accent_color, width: 120, marginTop: 16, borderRadius: 2 }} />
      </FadeIn>
      {items.map((item, i) => (
        <FadeIn key={i} frame={frame} delay={15 + i * 12}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <div style={{ width: 14, height: 14, borderRadius: '50%', backgroundColor: scene.accent_color, flexShrink: 0 }} />
            <p style={{ color: THEME.text, fontSize: 48, margin: 0, lineHeight: 1.4, fontFamily: 'system-ui' }}>{item}</p>
          </div>
        </FadeIn>
      ))}
    </AbsoluteFill>
  );
};

const DiagramScene: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const steps = scene.steps || scene.bullets || [];
  return (
    <AbsoluteFill style={{ backgroundColor: THEME.bg, padding: 80, flexDirection: 'column', justifyContent: 'center', gap: 28 }}>
      <FadeIn frame={frame}>
        <h2 style={{ color: THEME.text, fontSize: 68, fontWeight: 700, margin: 0, fontFamily: 'system-ui' }}>
          {scene.heading}
        </h2>
        <div style={{ height: 4, backgroundColor: scene.accent_color, width: 120, marginTop: 16, borderRadius: 2 }} />
      </FadeIn>
      {steps.map((step, i) => {
        const scale = spring({ frame: frame - (20 + i * 18), fps: 30, config: { damping: 12 } });
        return (
          <div key={i} style={{ transform: `scale(${scale})`, backgroundColor: THEME.surface, borderLeft: `6px solid ${scene.accent_color}`, padding: '24px 36px', borderRadius: 12 }}>
            <span style={{ color: THEME.muted, fontSize: 30, fontWeight: 600, fontFamily: 'system-ui' }}>0{i + 1}</span>
            <p style={{ color: THEME.text, fontSize: 50, fontWeight: 700, margin: '8px 0 0', fontFamily: 'system-ui' }}>{step}</p>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

const CTAScene: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: THEME.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 32, padding: 60 }}>
      <FadeIn frame={frame}>
        <div style={{ fontSize: 120, textAlign: 'center' }}>🤖</div>
      </FadeIn>
      <FadeIn frame={frame} delay={15}>
        <h1 style={{ color: THEME.text, fontSize: 72, fontWeight: 700, textAlign: 'center', margin: 0, fontFamily: 'system-ui' }}>
          {scene.heading}
        </h1>
      </FadeIn>
      {scene.subheading && (
        <FadeIn frame={frame} delay={28}>
          <p style={{ color: THEME.muted, fontSize: 44, textAlign: 'center', margin: 0, fontFamily: 'system-ui' }}>
            {scene.subheading}
          </p>
        </FadeIn>
      )}
      <FadeIn frame={frame} delay={40}>
        <div style={{ backgroundColor: scene.accent_color, paddingInline: 60, paddingBlock: 24, borderRadius: 60 }}>
          <p style={{ color: '#fff', fontSize: 44, fontWeight: 700, margin: 0, fontFamily: 'system-ui' }}>Theo dõi ngay! 👆</p>
        </div>
      </FadeIn>
    </AbsoluteFill>
  );
};

const SCENE_COMPONENTS: Record<string, React.FC<{ scene: SceneData }>> = {
  title: TitleScene,
  bullets: BulletsScene,
  diagram: DiagramScene,
  flow_chart: DiagramScene,
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
