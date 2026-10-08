import React from "react";
import { Audio, Img, useCurrentFrame, useVideoConfig } from "remotion";
import { CinematicBackdrop } from "../components/CinematicBackdrop";
import { easeOutCubic, remap, spring } from "../lib/easing";
import { resolveAsset } from "../lib/assets";
import { withAlpha } from "../lib/theme";
import type { SceneProps } from "./types";

export const BulletsScene: React.FC<SceneProps> = ({ scene, theme, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const heading = easeOutCubic(remap(frame, 0, fps * 0.55, 0, 1));
  const activeIndex = Math.min(scene.bullets.length - 1, Math.max(0, Math.floor((frame / Math.max(1, durationFrames)) * scene.bullets.length)));
  const hasSlide = scene.assets && scene.assets.length > 0 && scene.assets[0].endsWith(".png");
  const slideSrc = hasSlide ? resolveAsset(scene.assets[0]) : null;

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", display: "flex", alignItems: "center", background: theme.bg }}>
      <CinematicBackdrop accent={theme.accent} secondary={theme.secondary} />
      <div style={{ position: "relative", zIndex: 1, width: "100%", padding: "0 100px", display: "grid", gridTemplateColumns: hasSlide ? "0.95fr 1.05fr" : "0.8fr 1.2fr", gap: 60, alignItems: "center" }}>
        <section>
          <div style={{ color: theme.accent, fontFamily: theme.fontBody, fontSize: 18, fontWeight: 800, letterSpacing: ".16em", textTransform: "uppercase", opacity: heading }}>Key capability</div>
          <h2 style={{ fontFamily: theme.fontHeading, fontSize: hasSlide ? 56 : 72, fontWeight: 800, color: theme.text, lineHeight: 1.06, letterSpacing: "-.045em", margin: "16px 0 24px", opacity: heading, transform: `translateY(${(1 - heading) * 32}px)` }}>{scene.heading}</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 10 }}>
            {scene.bullets.map((bullet, index) => {
              const delay = fps * (0.2 + index * 0.14);
              const progress = spring(Math.max(0, (frame - delay) / fps), 170, 18);
              const isActive = index === activeIndex;
              return (
                <div
                  key={bullet}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 16,
                    padding: "14px 20px",
                    borderRadius: 14,
                    opacity: progress,
                    transform: `translateX(${(1 - progress) * 40}px)`,
                    background: isActive ? `linear-gradient(110deg, ${withAlpha(theme.accent, 0.22)}, rgba(255,255,255,0.04))` : "rgba(255,255,255,0.03)",
                    border: `1px solid ${isActive ? withAlpha(theme.accent, 0.6) : "rgba(255,255,255,0.08)"}`,
                  }}
                >
                  <div style={{ width: 34, height: 34, flexShrink: 0, borderRadius: 10, display: "grid", placeItems: "center", color: "#fff", font: "800 14px Inter, sans-serif", background: isActive ? `linear-gradient(135deg, ${theme.accent}, ${theme.secondary})` : "rgba(255,255,255,0.08)" }}>{String(index + 1).padStart(2, "0")}</div>
                  <p style={{ margin: 0, color: isActive ? theme.text : "#cbd5e1", fontFamily: theme.fontBody, fontWeight: isActive ? 600 : 450, fontSize: 24, lineHeight: 1.3 }}>{bullet}</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* Right side: Either slide card or large bullet cards */}
        {hasSlide && slideSrc ? (
          <section style={{ display: "flex", flexDirection: "column", alignItems: "center", opacity: heading, transform: `scale(${0.96 + heading * 0.04})` }}>
            <div
              style={{
                position: "relative",
                width: "100%",
                maxWidth: 820,
                borderRadius: 20,
                overflow: "hidden",
                border: `1px solid ${withAlpha("#ffffff", 0.16)}`,
                boxShadow: `0 35px 80px rgba(0,0,0,0.7), 0 0 40px ${withAlpha(theme.accent, 0.25)}`,
                transform: `translateY(${Math.sin(frame / fps * 0.8) * 6}px)`,
              }}
            >
              <Img src={slideSrc} style={{ width: "100%", display: "block", objectFit: "contain" }} />
              <div style={{ position: "absolute", top: 12, right: 14, background: "rgba(0,0,0,0.65)", backdropFilter: "blur(8px)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 100, padding: "4px 12px", display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: theme.accent }} />
                <span style={{ color: "#e2e8f0", fontSize: 11, fontWeight: 700, fontFamily: "Inter, sans-serif", letterSpacing: "0.06em" }}>PRESENTATION DECK</span>
              </div>
            </div>
          </section>
        ) : (
          <section style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {scene.bullets.map((bullet, index) => {
              const delay = fps * (0.22 + index * 0.16);
              const progress = spring(Math.max(0, (frame - delay) / fps), 170, 18);
              const isActive = index === activeIndex;
              return <BulletCard key={bullet} text={bullet} number={index + 1} progress={progress} active={isActive} theme={theme} />;
            })}
          </section>
        )}
      </div>
      {scene.audio_path && <Audio src={resolveAsset(scene.audio_path)} />}
    </div>
  );
};

const BulletCard: React.FC<{ text: string; number: number; progress: number; active: boolean; theme: SceneProps["theme"] }> = ({ text, number, progress, active, theme }) => (
  <div style={{
    minHeight: 108, display: "flex", alignItems: "center", gap: 28, padding: "23px 30px", borderRadius: 18,
    opacity: progress, transform: `translateX(${(1 - progress) * 70}px) scale(${active ? 1.018 : 1})`,
    background: active ? `linear-gradient(110deg, ${withAlpha(theme.accent, 0.23)}, ${withAlpha("#ffffff", 0.055)})` : "rgba(255,255,255,.035)",
    border: `1px solid ${active ? withAlpha(theme.accent, 0.65) : withAlpha("#ffffff", 0.1)}`,
    boxShadow: active ? `0 18px 48px ${withAlpha(theme.accent, 0.16)}` : "none",
  }}>
    <div style={{ width: 48, height: 48, flexShrink: 0, borderRadius: 14, display: "grid", placeItems: "center", color: active ? "#fff" : theme.textMuted, font: "800 17px Inter, sans-serif", background: active ? `linear-gradient(135deg, ${theme.accent}, ${theme.secondary})` : "rgba(255,255,255,.07)" }}>{String(number).padStart(2, "0")}</div>
    <p style={{ margin: 0, color: active ? theme.text : "#c5c7d2", fontFamily: theme.fontBody, fontWeight: active ? 650 : 500, fontSize: 31, lineHeight: 1.2 }}>{text}</p>
  </div>
);
