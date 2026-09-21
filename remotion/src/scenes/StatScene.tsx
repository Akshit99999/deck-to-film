/**
 * StatScene — animates a big number/stat with a ring motif.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, Audio } from "remotion";
import { spring, remap, easeOutCubic } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import type { SceneProps } from "./types";

export const StatScene: React.FC<SceneProps> = ({
  scene,
  theme,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const t = spring(frame / fps, 200, 16);
  const headingProgress = easeOutCubic(remap(frame, fps * 0.3, fps * 0.8, 0, 1));

  // Animate numeric value if stat_value is a number
  const rawValue = scene.stat_value || "100%";
  const numMatch = rawValue.match(/^(\d+(\.\d+)?)(.*)$/);
  let displayValue = rawValue;
  if (numMatch) {
    const target = parseFloat(numMatch[1]);
    const suffix = numMatch[3];
    const current = Math.round(target * Math.min(t, 1));
    displayValue = `${current}${suffix}`;
  }

  // Ring progress
  const ringRadius = 200;
  const ringCircumference = 2 * Math.PI * ringRadius;
  const ringProgress = Math.min(t, 1);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: theme.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        gap: 48,
        overflow: "hidden",
      }}
    >
      {/* Ring + stat */}
      <div style={{ position: "relative", width: 480, height: 480 }}>
        <svg
          width={480}
          height={480}
          style={{ position: "absolute", inset: 0 }}
        >
          {/* Track */}
          <circle
            cx={240}
            cy={240}
            r={ringRadius}
            fill="none"
            stroke={withAlpha(theme.accent, 0.15)}
            strokeWidth={16}
          />
          {/* Progress */}
          <circle
            cx={240}
            cy={240}
            r={ringRadius}
            fill="none"
            stroke={theme.accent}
            strokeWidth={16}
            strokeLinecap="round"
            strokeDasharray={ringCircumference}
            strokeDashoffset={ringCircumference * (1 - ringProgress)}
            transform="rotate(-90 240 240)"
            style={{ filter: `drop-shadow(0 0 12px ${theme.accent})` }}
          />
          {/* Glow dots */}
          {[0, 60, 120, 180, 240, 300].map((deg, i) => (
            <circle
              key={i}
              cx={240 + ringRadius * Math.cos((deg * Math.PI) / 180)}
              cy={240 + ringRadius * Math.sin((deg * Math.PI) / 180)}
              r={3}
              fill={withAlpha(theme.accent, 0.4)}
            />
          ))}
        </svg>

        {/* Center content */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              fontFamily: theme.fontHeading,
              fontSize: 96,
              fontWeight: 900,
              color: theme.text,
              lineHeight: 1,
              letterSpacing: "-0.04em",
            }}
          >
            {displayValue}
          </div>
          {scene.stat_label && (
            <div
              style={{
                fontFamily: theme.fontBody,
                fontSize: 24,
                color: theme.textMuted,
                fontWeight: 500,
                marginTop: 8,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              {scene.stat_label}
            </div>
          )}
        </div>
      </div>

      {/* Heading below */}
      <h2
        style={{
          fontFamily: theme.fontHeading,
          fontSize: 52,
          fontWeight: 700,
          color: theme.text,
          textAlign: "center",
          maxWidth: 900,
          opacity: headingProgress,
          transform: `translateY(${(1 - headingProgress) * 20}px)`,
          letterSpacing: "-0.02em",
          margin: 0,
        }}
      >
        {scene.heading}
      </h2>

      {/* Bullets */}
      {scene.bullets.length > 0 && (
        <div style={{ textAlign: "center" }}>
          {scene.bullets.map((b, i) => (
            <p
              key={i}
              style={{
                fontFamily: theme.fontBody,
                fontSize: 32,
                color: theme.textMuted,
                margin: "4px 0",
                opacity: headingProgress,
              }}
            >
              {b}
            </p>
          ))}
        </div>
      )}

      {scene.audio_path && <Audio src={scene.audio_path} />}
    </div>
  );
};
