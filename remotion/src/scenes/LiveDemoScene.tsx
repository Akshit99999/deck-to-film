/**
 * LiveDemoScene — recorded demo footage inside a 3D device frame.
 * Camera drifts, zooms into action regions, shows callout labels.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, Audio } from "remotion";
import { remap, easeOutCubic } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import { resolveAsset } from "../lib/assets";
import { DeviceFrame } from "../components/DeviceFrame";
import { CinematicBackdrop } from "../components/CinematicBackdrop";
import type { SceneProps } from "./types";

export const LiveDemoScene: React.FC<SceneProps> = ({
  scene,
  theme,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const introProgress = easeOutCubic(remap(frame, 0, fps * 0.6, 0, 1));

  const actions = scene.demo_actions || [];

  const hasDemoVideo = Boolean(scene.demo_video_path);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: theme.bg,
        overflow: "hidden",
      }}
    >
      <CinematicBackdrop accent={theme.accent} secondary={theme.secondary} intensity={0.95} />
      {/* Intro label */}
      <div
        style={{
          position: "absolute",
          top: 48,
          left: "50%",
          transform: `translateX(-50%)`,
          opacity: introProgress,
          zIndex: 20,
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 12,
            background: withAlpha(theme.accent, 0.15),
            border: `1px solid ${withAlpha(theme.accent, 0.4)}`,
            borderRadius: 100,
            padding: "10px 28px",
          }}
        >
          {/* Live dot */}
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: "#ef4444",
              boxShadow: "0 0 8px #ef4444",
              animation: "pulse 1s infinite",
            }}
          />
          <span
            style={{
              fontFamily: theme.fontBody,
              fontSize: 22,
              color: theme.text,
              fontWeight: 600,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}
          >
            Live Demo
          </span>
        </div>
        <h2
          style={{
            fontFamily: theme.fontHeading,
            fontSize: 40,
            fontWeight: 700,
            color: theme.text,
            textAlign: "center",
            marginTop: 16,
            opacity: introProgress,
          }}
        >
          {scene.heading}
        </h2>
      </div>

      {/* Demo video in device frame */}
      {hasDemoVideo ? (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            paddingTop: 140,
            paddingBottom: 40,
          }}
        >
          <DeviceFrame
            videoSrc={resolveAsset(scene.demo_video_path!)}
            deviceType="laptop"
            actions={actions}
            accentColor={theme.accent}
            durationFrames={durationFrames}
          />
        </div>
      ) : (
        <FallbackSlides scene={scene} theme={theme} frame={frame} fps={fps} />
      )}

      {scene.audio_path && <Audio src={resolveAsset(scene.audio_path)} />}
    </div>
  );
};

/**
 * A designed command-suite overview when an individual capture is unavailable.
 * It is intentionally useful rather than a warning card: viewers can still see
 * the complete product layout and how its operating surfaces fit together.
 */
const FallbackSlides: React.FC<{
  scene: any;
  theme: any;
  frame: number;
  fps: number;
}> = ({ scene, theme, frame, fps }) => {
  const t = easeOutCubic(remap(frame, 0, fps * 0.8, 0, 1));

  const fallbackAsset = (scene.assets && scene.assets.length > 0) ? scene.assets[0] : "slide_002.png";
  const src = resolveAsset(fallbackAsset);
  const modules = [
    ["Dashboard", "Overview & telemetry"],
    ["Live Cameras", "Multi-feed monitoring"],
    ["Alerts & Intel", "Threats & evidence"],
    ["Border Map", "GIS & sensor radar"],
    ["Netra Nain", "3D intelligence"],
    ["Operations Analytics", "Readiness & response"],
    ["Guard Duty & Log", "Sentries & handover"],
    ["Camera Settings", "Power & sensitivity"],
  ];

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        display: "flex",
        alignItems: "center", justifyContent: "center", padding: "150px 118px 80px",
      }}
    >
      <div style={{ display: "grid", gridTemplateColumns: "0.95fr 1.05fr", width: "100%", maxWidth: 1520, gap: 42, alignItems: "center", opacity: t, transform: `translateY(${(1 - t) * 24}px)` }}>
        <div style={{ position: "relative", border: `1px solid ${withAlpha(theme.accent, 0.42)}`, borderRadius: 18, overflow: "hidden", background: "#0b0e16", boxShadow: `0 30px 72px rgba(0,0,0,.58), 0 0 42px ${withAlpha(theme.accent, 0.15)}` }}>
          {src ? <img src={src} style={{ width: "100%", display: "block" }} alt="BorderLens platform" /> : <div style={{ aspectRatio: "16 / 10" }} />}
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(135deg, rgba(255,255,255,.13), transparent 28%, transparent)" }} />
          <div style={{ position: "absolute", left: 18, bottom: 18, padding: "8px 12px", background: "rgba(5,8,13,.78)", border: `1px solid ${withAlpha(theme.accent, 0.45)}`, color: "#f5f7fb", font: "800 14px Inter, sans-serif", letterSpacing: ".08em", textTransform: "uppercase" }}>BorderLens command suite</div>
        </div>
        <div>
          <div style={{ color: theme.accent, font: "800 16px Inter, sans-serif", letterSpacing: ".14em", textTransform: "uppercase", marginBottom: 14 }}>Full platform layout</div>
          <h3 style={{ color: theme.text, fontFamily: theme.fontHeading, fontSize: 46, lineHeight: 1.05, letterSpacing: "-.035em", margin: "0 0 24px" }}>One operational picture, from signal to response.</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {modules.map(([name, description], index) => {
              const item = easeOutCubic(remap(frame, fps * (0.22 + index * 0.06), fps * (0.65 + index * 0.06), 0, 1));
              return <div key={name} style={{ padding: "13px 15px", borderRadius: 11, background: "rgba(255,255,255,.055)", border: `1px solid ${withAlpha("#ffffff", 0.1)}`, opacity: item, transform: `translateX(${(1 - item) * 16}px)` }}><div style={{ color: theme.text, font: "700 17px Inter, sans-serif" }}>{name}</div><div style={{ color: theme.textMuted, font: "500 13px Inter, sans-serif", marginTop: 4 }}>{description}</div></div>;
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
