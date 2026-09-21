/**
 * OutroScene — call to action with animated accent burst.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, Audio } from "remotion";
import { spring, remap, easeOutCubic } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import type { SceneProps } from "./types";

export const OutroScene: React.FC<SceneProps> = ({
  scene,
  theme,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const t = spring(frame / fps, 160, 16);
  const headingProgress = easeOutCubic(remap(frame, fps * 0.2, fps * 0.8, 0, 1));
  const ctaProgress = easeOutCubic(remap(frame, fps * 0.6, fps * 1.1, 0, 1));

  // Outro fade-out
  const fadeOut = durationFrames > 0
    ? easeOutCubic(1 - remap(frame, durationFrames - fps * 0.5, durationFrames, 0, 1))
    : 1;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: theme.bg,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 40,
        overflow: "hidden",
        opacity: fadeOut,
      }}
    >
      {/* Burst rings */}
      {[1, 1.6, 2.2].map((scale, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            width: 600,
            height: 600,
            borderRadius: "50%",
            border: `1px solid ${withAlpha(theme.accent, 0.15 - i * 0.04)}`,
            transform: `scale(${t * scale})`,
            transformOrigin: "center",
          }}
        />
      ))}

      {/* Content */}
      <div style={{ position: "relative", zIndex: 10, textAlign: "center", maxWidth: 1000, padding: "0 80px" }}>
        <h2
          style={{
            fontFamily: theme.fontHeading,
            fontSize: 80,
            fontWeight: 900,
            color: theme.text,
            lineHeight: 1.05,
            marginBottom: 32,
            opacity: headingProgress,
            transform: `scale(${0.9 + headingProgress * 0.1})`,
            letterSpacing: "-0.03em",
          }}
        >
          {scene.heading}
        </h2>

        {scene.bullets.map((b, i) => (
          <p
            key={i}
            style={{
              fontFamily: theme.fontBody,
              fontSize: 36,
              color: theme.textMuted,
              margin: "8px 0",
              opacity: ctaProgress,
              transform: `translateY(${(1 - ctaProgress) * 16}px)`,
            }}
          >
            {b}
          </p>
        ))}

        {/* CTA button visual */}
        <div
          style={{
            display: "inline-block",
            marginTop: 48,
            padding: "20px 56px",
            background: `linear-gradient(135deg, ${theme.accent}, ${theme.secondary})`,
            borderRadius: 100,
            opacity: ctaProgress,
            transform: `scale(${0.95 + ctaProgress * 0.05})`,
            boxShadow: `0 8px 48px ${withAlpha(theme.accent, 0.5)}`,
          }}
        >
          <span
            style={{
              fontFamily: theme.fontBody,
              fontSize: 32,
              fontWeight: 700,
              color: "#fff",
              letterSpacing: "0.02em",
            }}
          >
            {scene.bullets[scene.bullets.length - 1] || "Get Started"}
          </span>
        </div>
      </div>

      {scene.audio_path && <Audio src={scene.audio_path} />}
    </div>
  );
};
