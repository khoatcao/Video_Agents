import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { Scene } from "../components/Scene";
import { TextOverlay } from "../components/TextOverlay";
import { DiagramBox } from "../components/DiagramBox";
import { Arrow } from "../components/Arrow";
import { theme } from "../styles/theme";

// ─────────────────────────────────────────────────────────────
//  Demo composition: "AI Agent là gì?" (What is an AI Agent?)
//  Total: 420 frames @ 30fps = 14 seconds (compressed demo)
//  Scenes:
//    Scene 1 —  0..89   (90 frames)  Title card
//    Scene 2 — 90..209  (120 frames) Agent + Tools diagram
//    Scene 3 — 210..329 (120 frames) Agent loop flow chart
//    Scene 4 — 330..419 (90 frames)  Summary
// ─────────────────────────────────────────────────────────────

const TOTAL_SCENES = 4;

// Canvas dimensions (1080 × 1920)
const W = 1080;
const H = 1920;

// ──────────────────────────────────────
// Scene 1: Title card
// ──────────────────────────────────────
const TitleScene: React.FC = () => (
  <Scene
    sceneNum={1}
    totalScenes={TOTAL_SCENES}
    durationFrames={90}
    globalStartFrame={0}
    description="Title card"
  >
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: `0 ${theme.spacing.xl}px`,
        gap: theme.spacing.md,
      }}
    >
      {/* Decorative top accent bar */}
      <div
        style={{
          width: 80,
          height: 6,
          borderRadius: 3,
          backgroundColor: theme.colors.primary,
          marginBottom: theme.spacing.sm,
        }}
      />

      {/* Main title */}
      <TextOverlay
        text="AI Agent là gì?"
        startFrame={5}
        fontSize={96}
        color={theme.colors.text}
        align="center"
        bold
      />

      {/* Subtitle */}
      <TextOverlay
        text="Tìm hiểu trong 60 giây"
        startFrame={15}
        fontSize={44}
        color={theme.colors.textMuted}
        align="center"
      />

      {/* Decorative robot emoji */}
      <TextOverlay
        text="🤖"
        startFrame={25}
        fontSize={120}
        align="center"
      />

      {/* Tagline */}
      <TextOverlay
        text="Hệ thống AI tự động lên kế hoạch & hành động"
        startFrame={35}
        fontSize={34}
        color={theme.colors.secondary}
        align="center"
      />
    </AbsoluteFill>
  </Scene>
);

// ──────────────────────────────────────
// Scene 2: Agent + Tools diagram
// ──────────────────────────────────────
const DiagramScene: React.FC = () => {
  // Layout: Agent center-box, tool boxes arranged around it
  // 1080 wide canvas; boxes are positioned absolutely

  const centerX = W / 2 - 140;   // center agent box left edge
  const centerY = H / 2 - 100;

  const agentW = 280;
  const agentH = 140;

  const toolW = 220;
  const toolH = 110;
  const toolGap = 160; // vertical gap between tool boxes on the right

  // Tool boxes — right column
  const toolX = centerX + agentW + 140;
  const searchY = centerY - toolGap;
  const codeY = centerY + (agentH - toolH) / 2;
  const apiY = centerY + toolH + toolGap / 2;

  // Arrow endpoints: center of agent right edge → center of tool left edge
  const agentRight = centerX + agentW;
  const agentCenterY = centerY + agentH / 2;

  return (
    <Scene
      sceneNum={2}
      totalScenes={TOTAL_SCENES}
      durationFrames={120}
      globalStartFrame={90}
      description="Agent tools diagram"
    >
      <AbsoluteFill style={{ padding: `${theme.spacing.lg}px ${theme.spacing.md}px` }}>
        {/* Section heading */}
        <div
          style={{
            position: "absolute",
            top: 80,
            left: 0,
            right: 0,
            textAlign: "center",
          }}
        >
          <TextOverlay
            text="AI Agent sử dụng Tools"
            startFrame={5}
            fontSize={62}
            color={theme.colors.text}
            align="center"
            bold
          />
          <TextOverlay
            text="để tương tác với thế giới"
            startFrame={12}
            fontSize={36}
            color={theme.colors.textMuted}
            align="center"
          />
        </div>

        {/* Agent center box */}
        <DiagramBox
          label="AI Agent"
          icon="🤖"
          startFrame={20}
          x={centerX}
          y={centerY}
          width={agentW}
          height={agentH}
          color={theme.colors.primary}
        />

        {/* Tool boxes */}
        <DiagramBox
          label="Search"
          icon="🔍"
          startFrame={20}
          x={toolX}
          y={searchY}
          width={toolW}
          height={toolH}
          color={theme.colors.secondary}
          delay={10}
        />
        <DiagramBox
          label="Code"
          icon="💻"
          startFrame={20}
          x={toolX}
          y={codeY}
          width={toolW}
          height={toolH}
          color={theme.colors.accent}
          delay={20}
        />
        <DiagramBox
          label="API"
          icon="🔌"
          startFrame={20}
          x={toolX}
          y={apiY}
          width={toolW}
          height={toolH}
          color={theme.colors.danger}
          delay={30}
        />

        {/* Arrows from agent to each tool */}
        <Arrow
          startFrame={45}
          x1={agentRight}
          y1={agentCenterY}
          x2={toolX}
          y2={searchY + toolH / 2}
          color={theme.colors.secondary}
        />
        <Arrow
          startFrame={50}
          x1={agentRight}
          y1={agentCenterY}
          x2={toolX}
          y2={codeY + toolH / 2}
          color={theme.colors.accent}
        />
        <Arrow
          startFrame={55}
          x1={agentRight}
          y1={agentCenterY}
          x2={toolX}
          y2={apiY + toolH / 2}
          color={theme.colors.danger}
        />

        {/* Caption */}
        <div
          style={{
            position: "absolute",
            bottom: 120,
            left: 0,
            right: 0,
            textAlign: "center",
          }}
        >
          <TextOverlay
            text="Agent chọn tool phù hợp cho từng nhiệm vụ"
            startFrame={70}
            fontSize={34}
            color={theme.colors.textMuted}
            align="center"
          />
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

// ──────────────────────────────────────
// Scene 3: Agent loop flow chart
// ──────────────────────────────────────
const LoopScene: React.FC = () => {
  // Vertical flow: Observe → Think → Act → Repeat
  const boxW = 380;
  const boxH = 120;
  const startX = W / 2 - boxW / 2;
  const topY = 220;
  const stepGap = 200; // vertical distance between box tops

  const observeY = topY;
  const thinkY = topY + stepGap;
  const actY = topY + stepGap * 2;
  const repeatY = topY + stepGap * 3;

  const boxCenterX = startX + boxW / 2;

  return (
    <Scene
      sceneNum={3}
      totalScenes={TOTAL_SCENES}
      durationFrames={120}
      globalStartFrame={210}
      description="Agent loop"
    >
      <AbsoluteFill>
        {/* Heading */}
        <div
          style={{
            position: "absolute",
            top: 60,
            left: 0,
            right: 0,
            textAlign: "center",
          }}
        >
          <TextOverlay
            text="Vòng lặp của Agent"
            startFrame={5}
            fontSize={62}
            color={theme.colors.text}
            align="center"
            bold
          />
        </div>

        {/* Step boxes */}
        <DiagramBox
          label="Observe"
          icon="👁️"
          startFrame={15}
          x={startX}
          y={observeY}
          width={boxW}
          height={boxH}
          color={theme.colors.primary}
        />
        <DiagramBox
          label="Think"
          icon="🧠"
          startFrame={15}
          x={startX}
          y={thinkY}
          width={boxW}
          height={boxH}
          color={theme.colors.accent}
          delay={10}
        />
        <DiagramBox
          label="Act"
          icon="⚡"
          startFrame={15}
          x={startX}
          y={actY}
          width={boxW}
          height={boxH}
          color={theme.colors.secondary}
          delay={20}
        />
        <DiagramBox
          label="Repeat"
          icon="🔄"
          startFrame={15}
          x={startX}
          y={repeatY}
          width={boxW}
          height={boxH}
          color={theme.colors.danger}
          delay={30}
        />

        {/* Vertical arrows between steps */}
        <Arrow
          startFrame={45}
          x1={boxCenterX}
          y1={observeY + boxH}
          x2={boxCenterX}
          y2={thinkY}
          color={theme.colors.textMuted}
        />
        <Arrow
          startFrame={55}
          x1={boxCenterX}
          y1={thinkY + boxH}
          x2={boxCenterX}
          y2={actY}
          color={theme.colors.textMuted}
        />
        <Arrow
          startFrame={65}
          x1={boxCenterX}
          y1={actY + boxH}
          x2={boxCenterX}
          y2={repeatY}
          color={theme.colors.textMuted}
        />

        {/* Loop-back arc label */}
        <div
          style={{
            position: "absolute",
            bottom: 100,
            left: 0,
            right: 0,
            textAlign: "center",
          }}
        >
          <TextOverlay
            text="Lặp lại cho đến khi hoàn thành nhiệm vụ"
            startFrame={80}
            fontSize={32}
            color={theme.colors.textMuted}
            align="center"
          />
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

// ──────────────────────────────────────
// Scene 4: Summary
// ──────────────────────────────────────
const SummaryScene: React.FC = () => (
  <Scene
    sceneNum={4}
    totalScenes={TOTAL_SCENES}
    durationFrames={90}
    globalStartFrame={330}
    description="Summary"
  >
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: `0 ${theme.spacing.lg}px`,
        gap: theme.spacing.md,
      }}
    >
      {/* Heading */}
      <TextOverlay
        text="Tóm lại:"
        startFrame={5}
        fontSize={56}
        color={theme.colors.primary}
        align="center"
        bold
      />

      {/* Key points */}
      <div
        style={{
          width: "100%",
          display: "flex",
          flexDirection: "column",
          gap: theme.spacing.sm,
          marginTop: theme.spacing.md,
        }}
      >
        {[
          { text: "✅  AI Agent tự đặt mục tiêu & lên kế hoạch", frame: 15 },
          { text: "✅  Sử dụng Tools để thực thi hành động", frame: 25 },
          { text: "✅  Vòng lặp: Observe → Think → Act", frame: 35 },
          { text: "✅  Không cần con người can thiệp từng bước", frame: 45 },
        ].map(({ text, frame }) => (
          <TextOverlay
            key={text}
            text={text}
            startFrame={frame}
            fontSize={38}
            color={theme.colors.text}
            align="left"
          />
        ))}
      </div>

      {/* CTA */}
      <TextOverlay
        text="Subscribe để học thêm về AI! 🚀"
        startFrame={60}
        fontSize={40}
        color={theme.colors.accent}
        align="center"
        bold
      />
    </AbsoluteFill>
  </Scene>
);

// ──────────────────────────────────────
// Root composition
// ──────────────────────────────────────
export const VideoComposition: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: theme.colors.background }}>
    <Sequence from={0} durationInFrames={90} name="Title">
      <TitleScene />
    </Sequence>

    <Sequence from={90} durationInFrames={120} name="Diagram">
      <DiagramScene />
    </Sequence>

    <Sequence from={210} durationInFrames={120} name="Loop">
      <LoopScene />
    </Sequence>

    <Sequence from={330} durationInFrames={90} name="Summary">
      <SummaryScene />
    </Sequence>
  </AbsoluteFill>
);
