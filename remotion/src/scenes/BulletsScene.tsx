/**
 * BulletsScene — animated bullet points with staggered entrance.
 * Each bullet slides in from the left with a spring, one by one.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, Audio } from "remotion";
import { spring, remap, easeOutCubic } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import type { SceneProps } from "./types";

export const BulletsScene: React.FC<SceneProps> = ({
  scene,
  theme,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headingProgress = easeOutCubic(remap(frame, 0, fps * 0.5, 0, 1));

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: theme.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      {/* Subtle left accent bar */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: 6,
          background: `linear-gradient(to bottom, transparent, ${theme.accent}, transparent)`,
          opacity: headingProgress,
        }}
      />

      <div
        style={{
          maxWidth: 1200,
          width: "100%",
          padding: "0 120px",
        }}
      >
        {/* Heading */}
        <h2
          style={{
            fontFamily: theme.fontHeading,
            fontSize: 64,
            fontWeight: 800,
            color: theme.text,
            marginBottom: 60,
            opacity: headingProgress,
            transform: `translateY(${(1 - headingProgress) * 30}px)`,
            letterSpacing: "-0.02em",
            lineHeight: 1.1,
          }}
        >
          {scene.heading}
        </h2>

        {/* Bullets */}
        <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          {scene.bullets.map((bullet, i) => {
            const delay = fps * (0.3 + i * 0.2);
            const bulletProgress = spring(
              Math.max(0, (frame - delay) / fps),
              180,
              18
            );
            return (
              <BulletItem
                key={i}
                text={bullet}
                index={i}
                progress={bulletProgress}
                accentColor={theme.accent}
                fontFamily={theme.fontBody}
              />
            );
          })}
        </div>
      </div>

      {/* Background glow */}
      <div
        style={{
          position: "absolute",
          right: "5%",
          bottom: "10%",
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${withAlpha(theme.accent, 0.08)} 0%, transparent 70%)`,
          filter: "blur(60px)",
          pointerEvents: "none",
        }}
      />

      {scene.audio_path && <Audio src={scene.audio_path} />}
    </div>
  );
};

const BulletItem: React.FC<{
  text: string;
  index: number;
  progress: number;
  accentColor: string;
  fontFamily: string;
}> = ({ text, index, progress, accentColor, fontFamily }) => (
  <div
    style={{
      display: "flex",
      alignItems: "flex-start",
      gap: 24,
      opacity: progress,
      transform: `translateX(${(1 - progress) * -40}px)`,
    }}
  >
    {/* Bullet dot */}
    <div
      style={{
        flexShrink: 0,
        width: 12,
        height: 12,
        borderRadius: "50%",
        background: accentColor,
        marginTop: 14,
        boxShadow: `0 0 12px ${accentColor}88`,
      }}
    />
    <p
      style={{
        fontFamily,
        fontSize: 44,
        fontWeight: 500,
        color: "#e8e8f0",
        lineHeight: 1.35,
        margin: 0,
      }}
    >
      {text}
    </p>
  </div>
);
