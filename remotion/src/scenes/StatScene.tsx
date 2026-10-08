import React from "react";
import { useCurrentFrame, useVideoConfig, Audio, Img } from "remotion";
import { spring, remap, easeOutCubic } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import { resolveAsset } from "../lib/assets";
import { CinematicBackdrop } from "../components/CinematicBackdrop";
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
  const hasSlide = scene.assets && scene.assets.length > 0 && scene.assets[0].endsWith(".png");
  const slideSrc = hasSlide ? resolveAsset(scene.assets[0]) : null;

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
  const ringRadius = hasSlide ? 160 : 200;
  const ringCircumference = 2 * Math.PI * ringRadius;
  const ringProgress = Math.min(t, 1);
  const ringSize = ringRadius * 2 + 80;

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
      <CinematicBackdrop accent={theme.accent} secondary={theme.secondary} />
      
      <div
        style={{
          position: "relative",
          zIndex: 1,
          width: "100%",
          padding: "0 100px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: hasSlide ? 80 : 48,
        }}
      >
        {/* Left / Center: Stat & Ring */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 32 }}>
          <div style={{ position: "relative", width: ringSize, height: ringSize }}>
            <svg
              width={ringSize}
              height={ringSize}
              style={{ position: "absolute", inset: 0 }}
            >
              {/* Track */}
              <circle
                cx={ringSize / 2}
                cy={ringSize / 2}
                r={ringRadius}
                fill="none"
                stroke={withAlpha(theme.accent, 0.15)}
                strokeWidth={14}
              />
              {/* Progress */}
              <circle
                cx={ringSize / 2}
                cy={ringSize / 2}
                r={ringRadius}
                fill="none"
                stroke={theme.accent}
                strokeWidth={14}
                strokeLinecap="round"
                strokeDasharray={ringCircumference}
                strokeDashoffset={ringCircumference * (1 - ringProgress)}
                transform={`rotate(-90 ${ringSize / 2} ${ringSize / 2})`}
                style={{ filter: `drop-shadow(0 0 12px ${theme.accent})` }}
              />
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
                  fontSize: hasSlide ? 84 : 112,
                  fontWeight: 900,
                  color: theme.text,
                  lineHeight: 1,
                  letterSpacing: "-0.04em",
                }}
              >
                {displayValue}
              </div>
              <div
                style={{
                  fontFamily: theme.fontBody,
                  fontSize: hasSlide ? 20 : 24,
                  fontWeight: 600,
                  color: theme.accent,
                  marginTop: 10,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
              >
                {scene.stat_label || "Hardware Reuse"}
              </div>
            </div>
          </div>

          <h2
            style={{
              fontFamily: theme.fontHeading,
              fontSize: hasSlide ? 42 : 56,
              fontWeight: 800,
              color: theme.text,
              textAlign: "center",
              maxWidth: hasSlide ? 500 : 800,
              margin: 0,
              opacity: headingProgress,
              transform: `translateY(${(1 - headingProgress) * 20}px)`,
              letterSpacing: "-0.02em",
            }}
          >
            {scene.heading}
          </h2>
        </div>

        {/* Right side: Slide presentation card */}
        {hasSlide && slideSrc && (
          <div
            style={{
              flex: 1,
              maxWidth: 820,
              borderRadius: 20,
              overflow: "hidden",
              border: "1px solid rgba(255,255,255,0.18)",
              boxShadow: `0 35px 80px rgba(0,0,0,0.75), 0 0 50px ${withAlpha(theme.accent, 0.25)}`,
              opacity: headingProgress,
              transform: `scale(${0.96 + headingProgress * 0.04}) translateY(${Math.sin(frame / fps * 0.8) * 6}px)`,
            }}
          >
            <Img src={slideSrc} style={{ width: "100%", display: "block", objectFit: "contain" }} />
          </div>
        )}
      </div>

      {scene.audio_path && <Audio src={resolveAsset(scene.audio_path)} />}
    </div>
  );
};
