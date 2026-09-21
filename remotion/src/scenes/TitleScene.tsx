/**
 * TitleScene — opening title card with 3D floating orb motif.
 */

import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  Audio,
  interpolate,
  Easing,
} from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { spring, easeOutCubic, remap } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import type { SceneProps } from "./types";

export const TitleScene: React.FC<SceneProps> = ({
  scene,
  theme,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleProgress = easeOutCubic(remap(frame, 0, fps * 0.6, 0, 1));
  const subtitleProgress = easeOutCubic(remap(frame, fps * 0.4, fps * 1.0, 0, 1));
  const orbProgress = spring(frame / fps, 120, 14);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: `radial-gradient(ellipse at 60% 40%, ${withAlpha(theme.accent, 0.18)} 0%, ${theme.bg} 70%)`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      {/* Animated background grid */}
      <GridBackground accent={theme.accent} frame={frame} fps={fps} />

      {/* Content */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          textAlign: "center",
          maxWidth: 1200,
          padding: "0 80px",
        }}
      >
        {/* Accent pill */}
        <div
          style={{
            display: "inline-block",
            background: withAlpha(theme.accent, 0.15),
            border: `1px solid ${withAlpha(theme.accent, 0.4)}`,
            borderRadius: 100,
            padding: "8px 24px",
            marginBottom: 32,
            opacity: titleProgress,
            transform: `translateY(${(1 - titleProgress) * 20}px)`,
          }}
        >
          <span
            style={{
              fontFamily: theme.fontBody,
              fontSize: 22,
              color: theme.accent,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            Product Demo
          </span>
        </div>

        {/* Main title */}
        <h1
          style={{
            fontFamily: theme.fontHeading,
            fontSize: 96,
            fontWeight: 800,
            color: theme.text,
            lineHeight: 1.05,
            margin: "0 0 32px",
            opacity: titleProgress,
            transform: `translateY(${(1 - titleProgress) * 40}px)`,
            letterSpacing: "-0.03em",
          }}
        >
          {scene.heading}
        </h1>

        {/* Narration excerpt as subtitle */}
        {scene.bullets[0] && (
          <p
            style={{
              fontFamily: theme.fontBody,
              fontSize: 32,
              color: theme.textMuted,
              fontWeight: 400,
              maxWidth: 800,
              margin: "0 auto",
              lineHeight: 1.5,
              opacity: subtitleProgress,
              transform: `translateY(${(1 - subtitleProgress) * 20}px)`,
            }}
          >
            {scene.bullets[0]}
          </p>
        )}
      </div>

      {/* Floating accent orb */}
      <div
        style={{
          position: "absolute",
          right: "10%",
          top: "15%",
          width: 480,
          height: 480,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${withAlpha(theme.accent, 0.3)} 0%, transparent 70%)`,
          transform: `scale(${orbProgress}) translateY(${Math.sin(frame / fps) * 12}px)`,
          filter: "blur(40px)",
        }}
      />

      {/* Audio */}
      {scene.audio_path && <Audio src={scene.audio_path} />}
    </div>
  );
};

const GridBackground: React.FC<{
  accent: string;
  frame: number;
  fps: number;
}> = ({ accent, frame, fps }) => {
  const opacity = remap(frame, 0, fps * 0.5, 0, 0.12);
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        opacity,
        backgroundImage: `
          linear-gradient(${withAlpha(accent, 0.4)} 1px, transparent 1px),
          linear-gradient(90deg, ${withAlpha(accent, 0.4)} 1px, transparent 1px)
        `,
        backgroundSize: "80px 80px",
        maskImage: "radial-gradient(ellipse at center, black 30%, transparent 80%)",
      }}
    />
  );
};
