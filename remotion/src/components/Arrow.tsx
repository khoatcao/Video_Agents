import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import { theme } from "../styles/theme";

interface ArrowProps {
  startFrame: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color?: string;
  label?: string;
  delay?: number;
}

export const Arrow: React.FC<ArrowProps> = ({
  startFrame,
  x1,
  y1,
  x2,
  y2,
  color = theme.colors.primary,
  label,
  delay = 0,
}) => {
  const frame = useCurrentFrame();

  const effectiveStart = startFrame + delay;
  const elapsed = frame - effectiveStart;

  // Animate the line drawing from 0% to 100% progress over 20 frames
  const progress = interpolate(elapsed, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Label fades in after line is drawn (frame 20+)
  const labelOpacity = interpolate(elapsed, [20, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (elapsed < 0) return null;

  // Compute the animated endpoint
  const currentX2 = x1 + (x2 - x1) * progress;
  const currentY2 = y1 + (y2 - y1) * progress;

  // Line length and angle for arrowhead
  const dx = x2 - x1;
  const dy = y2 - y1;
  const angle = Math.atan2(dy, dx) * (180 / Math.PI);
  const length = Math.sqrt(dx * dx + dy * dy);

  // Arrowhead size
  const arrowSize = 14;

  // Arrowhead only visible when progress > 0.9
  const arrowOpacity = interpolate(progress, [0.85, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Mid point for label
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;

  // Canvas dimensions — use parent's coordinate space via SVG with absolute positioning
  // We need a bounding box large enough to contain the arrow
  const padding = 40;
  const svgX = Math.min(x1, x2) - padding;
  const svgY = Math.min(y1, y2) - padding;
  const svgW = Math.abs(x2 - x1) + padding * 2;
  const svgH = Math.abs(y2 - y1) + padding * 2;

  // Adjust coordinates relative to SVG viewport
  const rx1 = x1 - svgX;
  const ry1 = y1 - svgY;
  const rcx2 = currentX2 - svgX;
  const rcy2 = currentY2 - svgY;
  const rfx2 = x2 - svgX;
  const rfy2 = y2 - svgY;

  return (
    <>
      <svg
        style={{
          position: "absolute",
          left: svgX,
          top: svgY,
          width: svgW,
          height: svgH,
          overflow: "visible",
          pointerEvents: "none",
        }}
        viewBox={`0 0 ${svgW} ${svgH}`}
      >
        <defs>
          <marker
            id={`arrowhead-${x1}-${y1}-${x2}-${y2}`}
            markerWidth={arrowSize}
            markerHeight={arrowSize}
            refX={arrowSize - 2}
            refY={arrowSize / 2}
            orient="auto"
          >
            <polygon
              points={`0 0, ${arrowSize} ${arrowSize / 2}, 0 ${arrowSize}`}
              fill={color}
              opacity={arrowOpacity}
            />
          </marker>
        </defs>

        {/* Glow / shadow line */}
        <line
          x1={rx1}
          y1={ry1}
          x2={rcx2}
          y2={rcy2}
          stroke={color}
          strokeWidth={6}
          strokeOpacity={0.25}
          strokeLinecap="round"
        />

        {/* Main line */}
        <line
          x1={rx1}
          y1={ry1}
          x2={rcx2}
          y2={rcy2}
          stroke={color}
          strokeWidth={3}
          strokeLinecap="round"
          markerEnd={
            progress > 0.85
              ? `url(#arrowhead-${x1}-${y1}-${x2}-${y2})`
              : undefined
          }
        />
      </svg>

      {/* Label — positioned absolutely in parent coordinate space */}
      {label && (
        <div
          style={{
            position: "absolute",
            left: midX,
            top: midY - 14,
            transform: "translate(-50%, -50%)",
            opacity: labelOpacity,
            backgroundColor: theme.colors.background,
            color: color,
            fontSize: 18,
            fontWeight: "bold",
            fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
            padding: "4px 10px",
            borderRadius: 8,
            border: `1.5px solid ${color}`,
            pointerEvents: "none",
            whiteSpace: "nowrap",
          }}
        >
          {label}
        </div>
      )}
    </>
  );
};
