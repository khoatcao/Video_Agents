import React from "react";
import { useCurrentFrame, interpolate, AbsoluteFill } from "remotion";
import { theme } from "../styles/theme";

interface SceneProps {
  sceneNum: number;
  totalScenes: number;
  durationFrames: number;
  globalStartFrame: number;
  description: string;
  children: React.ReactNode;
}

export const Scene: React.FC<SceneProps> = ({
  sceneNum,
  totalScenes,
  durationFrames,
  globalStartFrame,
  description,
  children,
}) => {
  const frame = useCurrentFrame();

  // Fade in over first 10 frames
  const fadeIn = interpolate(frame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Fade out over last 10 frames
  const fadeOut = interpolate(
    frame,
    [durationFrames - 10, durationFrames],
    [1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  const opacity = Math.min(fadeIn, fadeOut);

  // Progress bar width for scene position indicator
  const progressWidth = (sceneNum / totalScenes) * 100;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: theme.colors.background,
        opacity,
      }}
    >
      {/* Scene content */}
      <AbsoluteFill>{children}</AbsoluteFill>

      {/* Scene progress dots — bottom right */}
      <div
        style={{
          position: "absolute",
          bottom: 48,
          right: 48,
          display: "flex",
          flexDirection: "row",
          gap: 8,
          alignItems: "center",
        }}
      >
        {Array.from({ length: totalScenes }, (_, i) => (
          <div
            key={i}
            style={{
              width: i + 1 === sceneNum ? 24 : 8,
              height: 8,
              borderRadius: 4,
              backgroundColor:
                i + 1 === sceneNum
                  ? theme.colors.primary
                  : i + 1 < sceneNum
                  ? theme.colors.secondary
                  : theme.colors.border,
              transition: "all 0.3s ease",
            }}
          />
        ))}
      </div>

      {/* Scene number indicator — subtle, bottom left */}
      <div
        style={{
          position: "absolute",
          bottom: 44,
          left: 48,
          color: theme.colors.textMuted,
          fontSize: 22,
          fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
          fontWeight: "bold",
          letterSpacing: "0.05em",
          opacity: 0.6,
        }}
      >
        {String(sceneNum).padStart(2, "0")} / {String(totalScenes).padStart(2, "0")}
      </div>
    </AbsoluteFill>
  );
};
