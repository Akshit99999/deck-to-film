/**
 * SlideShowcaseScene — displays slide PNGs on floating 3D-style panels
 * with a parallax drift and soft glow border.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, Audio, Img } from "remotion";
import { spring, remap, easeOutCubic } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import { resolveAsset } from "../lib/assets";
import { CinematicBackdrop } from "../components/CinematicBackdrop";
import type { SceneProps } from "./types";

export const SlideShowcaseScene: React.FC<SceneProps> = ({
  scene,
  theme,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headingProgress = easeOutCubic(remap(frame, 0, fps * 0.5, 0, 1));
  const t = frame / fps;

  const slides = scene.assets.filter((a) => a.endsWith(".png")).slice(0, 3);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: theme.bg,
        display: "flex",
        alignItems: "center",
        overflow: "hidden",
      }}
    >
      <CinematicBackdrop accent={theme.accent} secondary={theme.secondary} />
      {/* Left: heading + bullets */}
      <div
        style={{
          position: "relative",
          zIndex: 1,
          width: "40%",
          padding: "0 0 0 100px",
          flexShrink: 0,
        }}
      >
        <h2
          style={{
            fontFamily: theme.fontHeading,
            fontSize: 56,
            fontWeight: 800,
            color: theme.text,
            lineHeight: 1.1,
            marginBottom: 32,
            opacity: headingProgress,
            transform: `translateX(${(1 - headingProgress) * -30}px)`,
            letterSpacing: "-0.02em",
          }}
        >
          {scene.heading}
        </h2>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {scene.bullets.map((b, i) => {
            const bp = easeOutCubic(remap(frame, fps * (0.4 + i * 0.15), fps * (0.9 + i * 0.15), 0, 1));
            return (
              <div
                key={i}
                style={{
                  fontFamily: theme.fontBody,
                  fontSize: 30,
                  color: theme.textMuted,
                  opacity: bp,
                  transform: `translateX(${(1 - bp) * -20}px)`,
                  paddingLeft: 20,
                  borderLeft: `3px solid ${withAlpha(theme.accent, 0.5)}`,
                }}
              >
                {b}
              </div>
            );
          })}
        </div>
      </div>

      {/* Right: floating slide panels */}
      <div
        style={{
          zIndex: 1,
          flex: 1,
          position: "relative",
          height: "100%",
        }}
      >
        {slides.length === 0 ? (
          <PlaceholderPanel theme={theme} t={t} index={0} />
        ) : (
          slides.map((src, i) => (
            <SlidePanel
              key={i}
              src={src}
              index={i}
              total={slides.length}
              t={t}
              fps={fps}
              frame={frame}
              accentColor={theme.accent}
            />
          ))
        )}
      </div>

      {scene.audio_path && <Audio src={resolveAsset(scene.audio_path)} />}
    </div>
  );
};

const SlidePanel: React.FC<{
  src: string;
  index: number;
  total: number;
  t: number;
  fps: number;
  frame: number;
  accentColor: string;
}> = ({ src, index, total, t, fps, frame, accentColor }) => {
  const delay = fps * (index * 0.2);
  const progress = spring(Math.max(0, (frame - delay) / fps), 150, 16);

  // If single slide, center it large and flat for maximum readability
  const isSingle = total === 1;
  const cardWidth = isSingle ? 860 : 640;
  const leftPos = isSingle ? 60 : index === 0 ? 30 : index === 1 ? 140 : 80;
  const topPos = isSingle ? 240 : index === 0 ? 120 : index === 1 ? 260 : 380;
  const rotAngle = isSingle ? 0 : index === 0 ? -3 : index === 1 ? 2 : -2;

  // Gentle float
  const floatY = Math.sin(t * 0.8 + index * 1.2) * 8;

  return (
    <div
      style={{
        position: "absolute",
        left: leftPos,
        top: topPos + floatY,
        width: cardWidth,
        transform: `perspective(1400px) rotateY(${isSingle ? -2 : 0}deg) rotate(${rotAngle}deg) scale(${progress})`,
        transformOrigin: "center center",
        opacity: progress,
        boxShadow: `0 35px 80px rgba(0,0,0,0.75), 0 0 50px ${accentColor}33`,
        border: `1px solid rgba(255,255,255,0.18)`,
        borderRadius: 20,
        overflow: "hidden",
        background: "#0a0a0f",
      }}
    >
      <Img
        src={resolveAsset(src)}
        style={{ width: "100%", display: "block", objectFit: "contain" }}
      />
    </div>
  );
};

const PlaceholderPanel: React.FC<{ theme: any; t: number; index: number }> = ({
  theme, t, index,
}) => {
  const floatY = Math.sin(t * 0.7) * 10;
  return (
    <div
      style={{
        position: "absolute",
        left: 100,
        top: 80 + floatY,
        width: 560,
        height: 315,
        background: withAlpha(theme.accent, 0.08),
        border: `2px solid ${withAlpha(theme.accent, 0.3)}`,
        borderRadius: 12,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <span style={{ color: theme.textMuted, fontFamily: theme.fontBody, fontSize: 20 }}>
        Slide preview
      </span>
    </div>
  );
};
