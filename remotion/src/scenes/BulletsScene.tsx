/** A chapter layout that turns factual bullets into paced editorial cards. */

import React from "react";
import { Audio, useCurrentFrame, useVideoConfig } from "remotion";
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

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", display: "flex", alignItems: "center", background: theme.bg }}>
      <CinematicBackdrop accent={theme.accent} secondary={theme.secondary} />
      <div style={{ position: "relative", zIndex: 1, width: "100%", padding: "0 118px", display: "grid", gridTemplateColumns: "0.8fr 1.2fr", gap: 76, alignItems: "center" }}>
        <section>
          <div style={{ color: theme.accent, fontFamily: theme.fontBody, fontSize: 18, fontWeight: 800, letterSpacing: ".16em", textTransform: "uppercase", opacity: heading }}>Key capability</div>
          <h2 style={{ fontFamily: theme.fontHeading, fontSize: 72, fontWeight: 800, color: theme.text, lineHeight: 1.04, letterSpacing: "-.045em", margin: "22px 0 30px", opacity: heading, transform: `translateY(${(1 - heading) * 32}px)` }}>{scene.heading}</h2>
          <p style={{ maxWidth: 480, margin: 0, color: theme.textMuted, fontFamily: theme.fontBody, fontSize: 24, lineHeight: 1.5, opacity: heading }}>
            A focused view of the operational details that make this work in practice.
          </p>
          <div style={{ display: "flex", gap: 9, marginTop: 42 }}>
            {scene.bullets.map((_, index) => <div key={index} style={{ width: index === activeIndex ? 38 : 12, height: 4, borderRadius: 8, background: index <= activeIndex ? theme.accent : withAlpha("#ffffff", 0.18), transition: "none" }} />)}
          </div>
        </section>
        <section style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {scene.bullets.map((bullet, index) => {
            const delay = fps * (0.22 + index * 0.16);
            const progress = spring(Math.max(0, (frame - delay) / fps), 170, 18);
            const isActive = index === activeIndex;
            return <BulletCard key={bullet} text={bullet} number={index + 1} progress={progress} active={isActive} theme={theme} />;
          })}
        </section>
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
