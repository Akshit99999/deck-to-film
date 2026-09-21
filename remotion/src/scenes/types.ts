/**
 * Shared TypeScript types for scene components.
 */

import type { Theme } from "../lib/theme";

export interface SceneData {
  index: number;
  type: string;
  heading: string;
  bullets: string[];
  narration: string;
  assets: string[];
  motif_3d: string;
  accent_color: string;
  transition_in: string;
  demo_flow: string | null;
  stat_value: string | null;
  stat_label: string | null;
  audio_path: string;
  duration_secs: number;
  demo_video_path?: string;
}

export interface PlanData {
  title: string;
  accent_color: string;
  secondary_color: string;
  font_heading: string;
  font_body: string;
  has_responsive_mobile: boolean;
}

export interface SceneProps {
  scene: SceneData;
  theme: Theme;
  durationFrames: number;
  srtContent?: string;
}

export interface VideoProps {
  plan: PlanData;
  scenes: SceneData[];
  srt_path: string;
  width: number;
  height: number;
  fps: number;
}
