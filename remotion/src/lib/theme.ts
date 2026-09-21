/**
 * Theme utilities — derive a consistent design system from plan colors.
 */

export interface Theme {
  accent: string;
  secondary: string;
  bg: string;
  bgAlt: string;
  text: string;
  textMuted: string;
  fontHeading: string;
  fontBody: string;
}

export function buildTheme(
  accent: string,
  secondary: string,
  fontHeading: string,
  fontBody: string,
): Theme {
  return {
    accent,
    secondary,
    bg: "#0a0a0f",
    bgAlt: "#12121a",
    text: "#f0f0ff",
    textMuted: "#8888aa",
    fontHeading: fontHeading || "Inter",
    fontBody: fontBody || "Inter",
  };
}

/** Convert hex to {r,g,b} 0-1 range for Three.js. */
export function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const clean = hex.replace("#", "");
  const n = parseInt(clean, 16);
  return {
    r: ((n >> 16) & 255) / 255,
    g: ((n >> 8) & 255) / 255,
    b: (n & 255) / 255,
  };
}

/** Alpha-blend hex color with black at given opacity. */
export function withAlpha(hex: string, alpha: number): string {
  const { r, g, b } = hexToRgb(hex);
  const ri = Math.round(r * 255);
  const gi = Math.round(g * 255);
  const bi = Math.round(b * 255);
  return `rgba(${ri},${gi},${bi},${alpha})`;
}
