/**
 * Remotion Root — registers VideoCaptioned and VideoClean compositions.
 *
 * Props are injected via --props remotion_props.json by the Python renderer.
 */

import React, { useMemo } from "react";
import {
  Composition,
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  getInputProps,
} from "remotion";
import { buildTheme, withAlpha } from "./lib/theme";
import { easeInOutCubic, remap } from "./lib/easing";
import { CaptionOverlay } from "./components/CaptionOverlay";
import { TitleScene } from "./scenes/TitleScene";
import { BulletsScene } from "./scenes/BulletsScene";
import { StatScene } from "./scenes/StatScene";
import { SlideShowcaseScene } from "./scenes/SlideShowcaseScene";
import { LiveDemoScene } from "./scenes/LiveDemoScene";
import { ArchitectureScene } from "./scenes/ArchitectureScene";
import { OutroScene } from "./scenes/OutroScene";
import type { SceneData, VideoProps } from "./scenes/types";

// ---------------------------------------------------------------------------
// Per-scene dispatch
// ---------------------------------------------------------------------------

const SceneDispatch: React.FC<{
  scene: SceneData;
  theme: ReturnType<typeof buildTheme>;
  durationFrames: number;
  timelineOffsetFrames: number;
  srtContent?: string;
  withCaptions: boolean;
}> = ({ scene, theme, durationFrames, timelineOffsetFrames, srtContent, withCaptions }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isDemoScene = scene.type === "live_demo";

  const Component = (() => {
    switch (scene.type) {
      case "title": return TitleScene;
      case "bullets": return BulletsScene;
      case "stat": return StatScene;
      case "slide_showcase": return SlideShowcaseScene;
      case "live_demo": return LiveDemoScene;
      case "architecture": return ArchitectureScene;
      case "outro": return OutroScene;
      default: return BulletsScene;
    }
  })();

  const entrance = easeInOutCubic(remap(frame, 0, Math.min(fps * 0.45, durationFrames * 0.12), 0, 1));
  const exit = easeInOutCubic(remap(frame, Math.max(0, durationFrames - fps * 0.32), durationFrames, 0, 1));
  const isWipe = scene.transition_in === "wipe";
  const isPush = scene.transition_in === "camera_push";
  const isDissolve = scene.transition_in === "dissolve";

  return (
    <AbsoluteFill
      style={{
        opacity: entrance * exit,
        transform: isPush
          ? `scale(${1.045 - entrance * 0.045})`
          : `translateY(${(1 - entrance) * (isDissolve ? 12 : 24)}px) scale(${isDissolve ? 0.985 + entrance * 0.015 : 1})`,
        clipPath: isWipe ? `inset(0 ${(1 - entrance) * 100}% 0 0)` : undefined,
      }}
    >
      <Component
        scene={scene}
        theme={theme}
        durationFrames={durationFrames}
      />
      {withCaptions && srtContent && (
        <CaptionOverlay
          srtContent={srtContent}
          accentColor={scene.accent_color || theme.accent}
          frameOffset={timelineOffsetFrames}
          liftForDemo={isDemoScene}
          cleanMode={false}
          fontSize={44}
        />
      )}
      {frame < 4 && (
        <div style={{ position: "absolute", inset: 0, background: withAlpha(scene.accent_color || theme.accent, (1 - frame / 4) * 0.12), pointerEvents: "none" }} />
      )}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Full video composition
// ---------------------------------------------------------------------------

const VideoComposition: React.FC<VideoProps & { withCaptions: boolean }> = ({
  plan,
  scenes,
  srt_path,
  fps,
  withCaptions,
}) => {
  const theme = buildTheme(
    plan.accent_color,
    plan.secondary_color,
    plan.font_heading,
    plan.font_body
  );

  // Load SRT content from props (passed as string in the JSON)
  const srtContent = (plan as any).srt_content || "";

  let offset = 0;
  return (
    <AbsoluteFill style={{ background: theme.bg, fontFamily: theme.fontBody }}>
      {scenes.map((scene) => {
        const durationSecs = scene.duration_secs || 10;
        const durationFrames = Math.round(durationSecs * fps);
        const from = offset;
        offset += durationFrames;

        return (
          <Sequence key={scene.index} from={from} durationInFrames={durationFrames}>
            <SceneDispatch
              scene={scene}
              theme={theme}
              durationFrames={durationFrames}
              timelineOffsetFrames={from}
              srtContent={srtContent}
              withCaptions={withCaptions}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Root export
// ---------------------------------------------------------------------------

const FALLBACK_SCENES: SceneData[] = [
  {
    index: 1,
    type: "title",
    heading: "Your Product",
    bullets: ["Add your pptx and repo to get started"],
    narration: "",
    assets: [],
    motif_3d: "floating_panels",
    accent_color: "#6366f1",
    transition_in: "crossfade",
    demo_flow: null,
    stat_value: null,
    stat_label: null,
    audio_path: "",
    duration_secs: 10,
  },
];

const FALLBACK_PLAN = {
  title: "Preview",
  accent_color: "#6366f1",
  secondary_color: "#818cf8",
  font_heading: "Inter",
  font_body: "Inter",
  has_responsive_mobile: false,
  srt_content: "",
};

const DEFAULT_PROPS: VideoProps = {
  plan: FALLBACK_PLAN,
  scenes: FALLBACK_SCENES,
  srt_path: "",
  width: 1920,
  height: 1080,
  fps: 30,
};

function totalFrames(scenes: SceneData[], fps: number): number {
  return scenes.reduce(
    (sum, s) => sum + Math.round((s.duration_secs || 10) * fps),
    0
  );
}

export const RemotionRoot: React.FC = () => {
  const fps = 30;
  const width = 1920;
  const height = 1080;

  // getInputProps() returns the --props JSON when rendering from CLI;
  // it returns {} in Studio (where we fall back to DEFAULT_PROPS).
  const inputProps = getInputProps() as Partial<VideoProps>;
  const scenes = (inputProps.scenes && inputProps.scenes.length > 0)
    ? inputProps.scenes
    : DEFAULT_PROPS.scenes;
  const plan = inputProps.plan ?? DEFAULT_PROPS.plan;

  const mergedProps: VideoProps = {
    ...DEFAULT_PROPS,
    ...inputProps,
    plan,
    scenes,
  };

  const total = Math.max(1, totalFrames(scenes, fps));

  return (
    <>
      <Composition
        id="VideoCaptioned"
        component={VideoComposition as any}
        defaultProps={{ ...mergedProps, withCaptions: true }}
        durationInFrames={total}
        fps={fps}
        width={width}
        height={height}
      />
      <Composition
        id="VideoClean"
        component={VideoComposition as any}
        defaultProps={{ ...mergedProps, withCaptions: false }}
        durationInFrames={total}
        fps={fps}
        width={width}
        height={height}
      />
    </>
  );
};
