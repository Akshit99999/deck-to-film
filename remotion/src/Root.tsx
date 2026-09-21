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
} from "remotion";
import { buildTheme } from "./lib/theme";
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
  srtContent?: string;
  withCaptions: boolean;
}> = ({ scene, theme, durationFrames, srtContent, withCaptions }) => {
  const frame = useCurrentFrame();
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

  return (
    <AbsoluteFill>
      <Component
        scene={scene}
        theme={theme}
        durationFrames={durationFrames}
      />
      {withCaptions && srtContent && (
        <CaptionOverlay
          srtContent={srtContent}
          accentColor={scene.accent_color || theme.accent}
          liftForDemo={isDemoScene}
          cleanMode={false}
          fontSize={44}
        />
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

  // When rendered from CLI, props are injected; in Studio we use defaults.
  const propsFromEnv = DEFAULT_PROPS;
  const total = totalFrames(propsFromEnv.scenes, fps);

  return (
    <>
      <Composition
        id="VideoCaptioned"
        component={VideoComposition as any}
        defaultProps={{ ...propsFromEnv, withCaptions: true }}
        durationInFrames={total}
        fps={fps}
        width={width}
        height={height}
      />
      <Composition
        id="VideoClean"
        component={VideoComposition as any}
        defaultProps={{ ...propsFromEnv, withCaptions: false }}
        durationInFrames={total}
        fps={fps}
        width={width}
        height={height}
      />
    </>
  );
};
