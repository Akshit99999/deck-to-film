/**
 * TitleScene — opening title card with 3D floating orb motif.
 */

import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  Audio,
  Img,
  interpolate,
  Easing,
} from "remotion";
import { spring, easeOutCubic, remap } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import { resolveAsset } from "../lib/assets";
import { CinematicBackdrop } from "../components/CinematicBackdrop";
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
  const hasSlide = scene.assets && scene.assets.length > 0 && scene.assets[0].endsWith(".png");
  const slideSrc = hasSlide ? resolveAsset(scene.assets[0]) : null;

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
      <CinematicBackdrop accent={theme.accent} secondary={theme.secondary} intensity={1.15} />
      {/* Animated background grid */}
      <GridBackground accent={theme.accent} frame={frame} fps={fps} />

      {/* Content */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          textAlign: "center",
          maxWidth: hasSlide ? 1400 : 1200,
          padding: "0 60px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
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
            marginBottom: hasSlide ? 16 : 32,
            opacity: titleProgress,
            transform: `translateY(${(1 - titleProgress) * 20}px)`,
          }}
        >
          <span
            style={{
              fontFamily: theme.fontBody,
              fontSize: 20,
              color: theme.accent,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            Product Showcase
          </span>
        </div>

        {/* Main title */}
        <h1
          style={{
            fontFamily: theme.fontHeading,
            fontSize: hasSlide ? 64 : 104,
            fontWeight: 800,
            color: theme.text,
            lineHeight: 1.05,
            margin: hasSlide ? "0 0 20px" : "0 0 32px",
            opacity: titleProgress,
            transform: `translateY(${(1 - titleProgress) * 40}px)`,
            letterSpacing: "-0.03em",
          }}
        >
          {scene.heading}
        </h1>

        {/* Featured Slide Card */}
        {hasSlide && slideSrc ? (
          <div
            style={{
              position: "relative",
              width: "100%",
              maxWidth: 880,
              borderRadius: 22,
              overflow: "hidden",
              border: `1px solid ${withAlpha("#ffffff", 0.2)}`,
              boxShadow: `0 35px 90px rgba(0,0,0,0.8), 0 0 50px ${withAlpha(theme.accent, 0.3)}`,
              opacity: subtitleProgress,
              transform: `scale(${0.95 + subtitleProgress * 0.05}) translateY(${Math.sin(frame / fps * 0.7) * 5}px)`,
            }}
          >
            <Img src={slideSrc} style={{ width: "100%", display: "block", objectFit: "contain" }} />
          </div>
        ) : (
          scene.bullets[0] && (
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
          )
        )}
      </div>

      {/* Floating accent orb */}
      <div
        style={{
          position: "absolute",
          right: "6%",
          top: "15%",
          width: 620,
          height: 620,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${withAlpha(theme.accent, 0.3)} 0%, transparent 70%)`,
          transform: `scale(${orbProgress}) translateY(${Math.sin(frame / fps) * 12}px)`,
          filter: "blur(40px)",
        }}
      />

      {/* Audio */}
      {scene.audio_path && <Audio src={resolveAsset(scene.audio_path)} />}
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
