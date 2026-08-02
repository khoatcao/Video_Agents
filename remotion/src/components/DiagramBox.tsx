import React from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";
import { theme } from "../styles/theme";

interface DiagramBoxProps {
  label: string;
  startFrame: number;
  x: number;
  y: number;
  width: number;
  height: number;
  color?: string;       // border + label color
  icon?: string;        // emoji icon
  delay?: number;       // extra frame delay
}

export const DiagramBox: React.FC<DiagramBoxProps> = ({
  label,
  startFrame,
  x,
  y,
  width,
  height,
  color = theme.colors.primary,
  icon,
  delay = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const effectiveStart = startFrame + delay;
  const elapsed = frame - effectiveStart;

  // Spring scale-in from 0 → 1
  const scale = spring({
    fps,
    frame: elapsed,
    config: {
      damping: 14,
      stiffness: 150,
      mass: 0.7,
    },
    from: 0,
    to: 1,
  });

  if (elapsed < 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        height,
        transform: `scale(${scale})`,
        transformOrigin: "center center",
        backgroundColor: theme.colors.boxBg,
        border: `3px solid ${color}`,
        borderRadius: 16,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        boxShadow: `0 0 24px ${color}33, 0 4px 16px rgba(0,0,0,0.4)`,
        padding: "12px 16px",
        boxSizing: "border-box",
      }}
    >
      {icon && (
        <span
          style={{
            fontSize: Math.min(height * 0.35, 48),
            lineHeight: 1,
          }}
        >
          {icon}
        </span>
      )}
      <span
        style={{
          color,
          fontSize: Math.max(14, Math.min(22, width * 0.12)),
          fontWeight: "bold",
          fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
          textAlign: "center",
          letterSpacing: "-0.01em",
          lineHeight: 1.2,
        }}
      >
        {label}
      </span>
    </div>
  );
};
