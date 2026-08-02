import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";
import { theme } from "../styles/theme";

interface TextOverlayProps {
  text: string;
  startFrame: number;
  fontSize?: number;
  color?: string;
  align?: "left" | "center" | "right";
  bold?: boolean;
}

export const TextOverlay: React.FC<TextOverlayProps> = ({
  text,
  startFrame,
  fontSize = 48,
  color = theme.colors.text,
  align = "center",
  bold = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Frames elapsed since this text started
  const elapsed = frame - startFrame;

  // Fade in over 20 frames using spring for smooth easing
  const opacity = interpolate(elapsed, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Slide up: start 40px below final position, reach 0 offset by frame 20
  const translateY = spring({
    fps,
    frame: elapsed,
    config: {
      damping: 14,
      stiffness: 120,
      mass: 0.8,
    },
    from: 40,
    to: 0,
  });

  if (elapsed < 0) return null;

  return (
    <div
      style={{
        opacity,
        transform: `translateY(${translateY}px)`,
        fontSize,
        fontWeight: bold ? "bold" : "normal",
        color,
        textAlign: align,
        fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
        lineHeight: 1.3,
        letterSpacing: bold ? "-0.02em" : "0",
        textShadow: "0 2px 12px rgba(0,0,0,0.5)",
      }}
    >
      {text}
    </div>
  );
};
