/**
 * SlideShowcaseScene — displays slide PNGs on floating 3D-style panels
 * with a parallax drift and soft glow border.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, Audio, Img } from "remotion";
import { spring, remap, easeOutCubic } from "../lib/easing";
import { withAlpha } from "../lib/theme";
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
        background: `radial-gradient(ellipse at 30% 60%, ${withAlpha(theme.accent, 0.1)} 0%, ${theme.bg} 60%)`,
        display: "flex",
        alignItems: "center",
        overflow: "hidden",
      }}
    >
      {/* Left: heading + bullets */}
      <div
        style={{
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

      {scene.audio_path && <Audio src={scene.audio_path} />}
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
  const delay = fps * (index * 0.25);
  const progress = spring(Math.max(0, (frame - delay) / fps), 150, 16);

  // Position: fan out 3 slides
  const positions = [
    { x: 60, y: -80, rot: -8, z: 0.9 },
    { x: 200, y: 60, rot: 3, z: 1.0 },
    { x: 80, y: 200, rot: 6, z: 0.85 },
  ];
  const pos = positions[index % positions.length];

  // Gentle float
  const floatY = Math.sin(t * 0.8 + index * 1.2) * 12;
  const floatRot = Math.sin(t * 0.5 + index * 0.8) * 1.5;

  return (
    <div
      style={{
        position: "absolute",
        left: pos.x,
        top: pos.y + floatY,
        width: 560,
        transform: `rotate(${pos.rot + floatRot}deg) scale(${progress * pos.z})`,
        transformOrigin: "center center",
        opacity: progress,
        filter: `drop-shadow(0 24px 48px rgba(0,0,0,0.7)) drop-shadow(0 0 20px ${accentColor}33)`,
        border: `2px solid ${accentColor}44`,
        borderRadius: 12,
        overflow: "hidden",
        background: "#0a0a0f",
      }}
    >
      <Img
        src={src}
        style={{ width: "100%", display: "block" }}
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
