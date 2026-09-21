/**
 * LiveDemoScene — recorded demo footage inside a 3D device frame.
 * Camera drifts, zooms into action regions, shows callout labels.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, Audio, Video, OffthreadVideo } from "remotion";
import { remap, easeOutCubic, spring } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import { DeviceFrame } from "../components/DeviceFrame";
import type { SceneProps } from "./types";

export const LiveDemoScene: React.FC<SceneProps> = ({
  scene,
  theme,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const introProgress = easeOutCubic(remap(frame, 0, fps * 0.6, 0, 1));

  // Parse actions from demo video sidecar if available
  const actions: any[] = [];

  const hasDemoVideo = Boolean(scene.demo_video_path);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: `radial-gradient(ellipse at 50% 30%, ${withAlpha(theme.accent, 0.12)} 0%, #050508 60%)`,
        overflow: "hidden",
      }}
    >
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
            videoSrc={scene.demo_video_path!}
            deviceType="laptop"
            actions={actions}
            accentColor={theme.accent}
            durationFrames={durationFrames}
          />
        </div>
      ) : (
        <FallbackSlides scene={scene} theme={theme} frame={frame} fps={fps} />
      )}

      {scene.audio_path && <Audio src={scene.audio_path} />}
    </div>
  );
};

/** Shown when no demo video was captured — uses slide screenshots with zoom/pan. */
const FallbackSlides: React.FC<{
  scene: any;
  theme: any;
  frame: number;
  fps: number;
}> = ({ scene, theme, frame, fps }) => {
  const t = remap(frame, 0, fps * 5, 0, 1);
  const scale = 1 + easeOutCubic(t) * 0.08;
  const translateX = easeOutCubic(t) * -40;

  const src = scene.assets[0];
  if (!src) return null;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        paddingTop: 160,
      }}
    >
      <div
        style={{
          transform: `scale(${scale}) translateX(${translateX}px)`,
          transformOrigin: "center center",
          width: "80%",
          border: `2px solid ${withAlpha(theme.accent, 0.4)}`,
          borderRadius: 12,
          overflow: "hidden",
          boxShadow: `0 32px 80px rgba(0,0,0,0.8), 0 0 40px ${withAlpha(theme.accent, 0.2)}`,
        }}
      >
        <img src={src} style={{ width: "100%", display: "block" }} alt="demo" />
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 48,
          left: "50%",
          transform: "translateX(-50%)",
          background: withAlpha("#ef4444", 0.85),
          color: "#fff",
          borderRadius: 8,
          padding: "8px 20px",
          fontFamily: theme.fontBody,
          fontSize: 18,
          fontWeight: 600,
        }}
      >
        ⚠ Live demo not available — showing static screenshots
      </div>
    </div>
  );
};
