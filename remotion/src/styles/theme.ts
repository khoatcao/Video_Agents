export const theme = {
  colors: {
    background: "#0f172a",   // dark navy (ByteByteGo style)
    primary: "#3b82f6",      // blue
    secondary: "#10b981",    // green
    accent: "#f59e0b",       // amber
    danger: "#ef4444",       // red
    text: "#f8fafc",         // white
    textMuted: "#94a3b8",    // gray
    boxBg: "#1e293b",        // box background
    border: "#334155",       // border color
  },
  fonts: {
    heading: "bold",
    body: "normal",
  },
  spacing: {
    xs: 8,
    sm: 16,
    md: 24,
    lg: 40,
    xl: 64,
  },
} as const;

export type Theme = typeof theme;
export type ThemeColor = keyof typeof theme.colors;
