import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { withAlpha } from "../lib/theme";

/** A subtle, deterministic layer of depth shared by the motion scenes. */
export const CinematicBackdrop: React.FC<{
  accent: string;
  secondary: string;
  intensity?: number;
}> = ({ accent, secondary, intensity = 1 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const driftX = Math.sin(t * 0.23) * 6;
  const driftY = Math.cos(t * 0.19) * 5;

  return (
    <>
      <div
        style={{
          position: "absolute", inset: -80, pointerEvents: "none", opacity: 0.9 * intensity,
          background: `radial-gradient(ellipse 58% 54% at ${68 + driftX}% ${18 + driftY}%, ${withAlpha(accent, 0.22)} 0%, transparent 68%), radial-gradient(ellipse 42% 44% at ${14 - driftX}% ${84 - driftY}%, ${withAlpha(secondary, 0.14)} 0%, transparent 72%), linear-gradient(135deg, #06070b 0%, #0c0d15 48%, #06070b 100%)`,
        }}
      />
      <div
        style={{
          position: "absolute", inset: 0, pointerEvents: "none", opacity: 0.18 * intensity,
          backgroundImage: `linear-gradient(${withAlpha("#ffffff", 0.12)} 1px, transparent 1px), linear-gradient(90deg, ${withAlpha("#ffffff", 0.12)} 1px, transparent 1px)`,
          backgroundSize: "96px 96px", maskImage: "radial-gradient(ellipse at center, black, transparent 78%)",
        }}
      />
      <div
        style={{
          position: "absolute", inset: 0, pointerEvents: "none", opacity: 0.055,
          backgroundImage: "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 160 160' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.75'/%3E%3C/svg%3E\")",
          mixBlendMode: "soft-light",
        }}
      />
    </>
  );
};
