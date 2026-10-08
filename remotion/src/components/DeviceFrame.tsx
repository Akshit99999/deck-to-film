/**
 * Content-first demo presentation. The recording is deliberately kept crisp
 * and front-facing; depth comes from the chassis, lighting, and camera move,
 * not by hiding the product inside a decorative 3D scene.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, Video, OffthreadVideo, Loop } from "remotion";
import { easeInOutCubic, remap, spring } from "../lib/easing";
import { withAlpha } from "../lib/theme";
import type { DemoAction } from "../scenes/types";

interface DeviceFrameProps {
  videoSrc: string;
  deviceType: "laptop" | "phone";
  actions: DemoAction[];
  accentColor: string;
  durationFrames: number;
}

export const DeviceFrame: React.FC<DeviceFrameProps> = ({
  videoSrc,
  deviceType,
  actions,
  accentColor,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const currentMs = (frame / fps) * 1000;
  const intro = spring(Math.min(frame / fps, 1.2), 145, 18);
  const activeAction = actions
    .filter((action) => Math.abs(action.timestamp_ms - currentMs) < 900)
    .sort((a, b) => Math.abs(a.timestamp_ms - currentMs) - Math.abs(b.timestamp_ms - currentMs))[0];
  const actionFocus = activeAction
    ? easeInOutCubic(remap(currentMs, activeAction.timestamp_ms - 450, activeAction.timestamp_ms + 250, 0, 1))
    : 0;
  const idle = Math.sin(frame / fps * 0.7);
  const rotationY = (activeAction ? 0 : idle * 1.5) + (1 - intro) * -8;
  const rotationX = (activeAction ? 0.8 : 2.2) + (1 - intro) * 4;
  const scale = 0.89 + intro * 0.11 + actionFocus * 0.025;
  const screenW = deviceType === "phone" ? Math.min(width * 0.31, 520) : Math.min(width * 0.73, 1360);
  const screenH = deviceType === "phone" ? screenW * 2.02 : screenW / (16 / 10);
  const stageY = deviceType === "phone" ? 22 : 66;

  return (
    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", perspective: 1800 }}>
      <div
        style={{
          position: "absolute", width: screenW * 1.2, height: screenH * 0.98,
          borderRadius: "50%", background: `radial-gradient(ellipse, ${withAlpha(accentColor, 0.31)} 0%, transparent 67%)`,
          filter: "blur(28px)", transform: `translateY(${stageY + 120}px)`, opacity: intro,
        }}
      />
      <div
        style={{
          position: "relative", width: screenW, height: screenH,
          transform: `translateY(${stageY + (1 - intro) * 76}px) scale(${scale}) rotateX(${rotationX}deg) rotateY(${rotationY}deg)`,
          transformStyle: "preserve-3d", opacity: intro, zIndex: 2,
        }}
      >
        <div
          style={{
            position: "absolute", inset: -15, padding: 15, borderRadius: deviceType === "phone" ? 44 : 28,
            background: "linear-gradient(145deg, #4b5060 0%, #171a22 21%, #050609 78%, #393f4e 100%)",
            boxShadow: `0 56px 90px rgba(0,0,0,.66), 0 0 0 1px ${withAlpha("#ffffff", 0.12)}, 0 0 60px ${withAlpha(accentColor, 0.22)}`,
          }}
        >
          <div style={{ position: "absolute", inset: 2, borderRadius: "inherit", border: `1px solid ${withAlpha("#ffffff", 0.2)}`, pointerEvents: "none" }} />
          {deviceType === "laptop" && <CameraDot />}
          <div
            style={{
              position: "relative", width: "100%", height: "100%", overflow: "hidden",
              borderRadius: deviceType === "phone" ? 31 : 13, background: "#080a0f",
              boxShadow: "inset 0 0 0 1px rgba(255,255,255,.09)",
              display: "flex", flexDirection: "column",
            }}
          >
            {/* Top Browser Window Bar */}
            {deviceType === "laptop" && (
              <div
                style={{
                  height: 38,
                  background: "#131620",
                  borderBottom: "1px solid rgba(255,255,255,0.08)",
                  display: "flex",
                  alignItems: "center",
                  padding: "0 14px",
                  gap: 12,
                  flexShrink: 0,
                  zIndex: 10,
                }}
              >
                <div style={{ display: "flex", gap: 7 }}>
                  <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ff5f57" }} />
                  <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ffbd2e" }} />
                  <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#27c840" }} />
                </div>
                <div
                  style={{
                    flex: 1,
                    maxWidth: 520,
                    margin: "0 auto",
                    height: 24,
                    background: "rgba(0,0,0,0.45)",
                    borderRadius: 6,
                    border: "1px solid rgba(255,255,255,0.07)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6,
                    fontSize: 12,
                    color: "#94a3b8",
                    fontFamily: "Inter, sans-serif",
                  }}
                >
                  <span style={{ fontSize: 10, opacity: 0.7 }}>🔒</span>
                  <span>border-lens.vercel.app</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 8px #10b981" }} />
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#10b981", fontFamily: "Inter, sans-serif", letterSpacing: "0.06em" }}>LIVE</span>
                </div>
              </div>
            )}
            <div style={{ flex: 1, position: "relative", width: "100%", height: "100%", overflow: "hidden" }}>
              <Loop durationInFrames={240}>
                <OffthreadVideo src={videoSrc} volume={0} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              </Loop>
              <div style={{ position: "absolute", inset: 0, background: "linear-gradient(118deg, rgba(255,255,255,.12) 0%, transparent 19%, transparent 69%, rgba(255,255,255,.04) 100%)", pointerEvents: "none", mixBlendMode: "screen" }} />
              {activeAction && <ActionFocus action={activeAction} accentColor={accentColor} progress={actionFocus} />}
            </div>
          </div>
        </div>
        {deviceType === "laptop" && <LaptopBase width={screenW} accentColor={accentColor} />}
      </div>
      <div
        style={{
          position: "absolute", bottom: 38, display: "flex", alignItems: "center", gap: 10,
          padding: "10px 16px", borderRadius: 100, background: "rgba(8,10,15,.68)",
          border: `1px solid ${withAlpha(accentColor, 0.34)}`, boxShadow: "0 14px 34px rgba(0,0,0,.32)", opacity: Math.min(1, intro * 1.2),
        }}
      >
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: accentColor, boxShadow: `0 0 12px ${accentColor}` }} />
        <span style={{ color: "#d6d9e4", fontFamily: "Inter, sans-serif", fontSize: 16, fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase" }}>Product walkthrough</span>
      </div>
    </div>
  );
};

const CameraDot: React.FC = () => (
  <div style={{ position: "absolute", top: 6, left: "50%", width: 7, height: 7, marginLeft: -3.5, borderRadius: "50%", background: "#06070a", boxShadow: "0 0 0 1px rgba(255,255,255,.12)" }} />
);

const LaptopBase: React.FC<{ width: number; accentColor: string }> = ({ width, accentColor }) => (
  <div
    style={{
      position: "absolute", width: width * 1.1, height: 34, left: "50%", bottom: -46, transform: "translateX(-50%) rotateX(54deg)",
      transformOrigin: "top", borderRadius: "2px 2px 18px 18px", background: "linear-gradient(180deg, #5b6371, #171a21 58%, #090a0d)",
      boxShadow: `0 20px 32px rgba(0,0,0,.45), 0 0 24px ${withAlpha(accentColor, 0.12)}`,
    }}
  >
    <div style={{ width: "21%", height: 5, margin: "6px auto", borderRadius: 20, background: "rgba(0,0,0,.42)" }} />
  </div>
);

const ActionFocus: React.FC<{ action: DemoAction; accentColor: string; progress: number }> = ({ action, accentColor, progress }) => {
  const left = `${Math.max(0, Math.min(96, (action.x / 1920) * 100))}%`;
  const top = `${Math.max(0, Math.min(94, (action.y / 1080) * 100))}%`;
  const width = `${Math.max(2.8, Math.min(42, (action.width / 1920) * 100))}%`;
  const height = `${Math.max(3.5, Math.min(38, (action.height / 1080) * 100))}%`;
  const label = action.narration_cue.split(" ").slice(0, 5).join(" ");
  return (
    <div style={{ position: "absolute", left, top, width, height, opacity: progress, transform: `scale(${0.94 + progress * 0.06})`, transformOrigin: "center" }}>
      <div style={{ position: "absolute", inset: -8, borderRadius: 10, border: `2px solid ${accentColor}`, boxShadow: `0 0 0 5px ${withAlpha(accentColor, 0.16)}, 0 0 24px ${withAlpha(accentColor, 0.75)}` }} />
      <div style={{ position: "absolute", top: -38, left: 0, padding: "6px 10px", borderRadius: 7, background: accentColor, color: "white", font: "700 13px Inter, sans-serif", whiteSpace: "nowrap", boxShadow: `0 8px 18px ${withAlpha(accentColor, 0.35)}` }}>{label}</div>
    </div>
  );
};
