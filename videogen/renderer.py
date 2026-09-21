"""Renderer — orchestrates Remotion to produce the final video.

Writes build/remotion_props.json, calls `npx remotion render`,
assembles the contact sheet, and embeds SRT as a soft subtitle track.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from videogen.captions import SceneAudio  # reuse type
from videogen.config import RenderConfig, Settings
from videogen.planner import VideoPlan
from videogen.voice import SceneAudio

logger = logging.getLogger(__name__)
console = Console()


class Renderer:
    """Drives Remotion to render the final video."""

    def __init__(self, cfg: Settings, remotion_dir: Path) -> None:
        self.cfg = cfg
        self.render_cfg: RenderConfig = cfg.render
        self.remotion_dir = remotion_dir

    def render(
        self,
        plan: VideoPlan,
        scene_audios: list[SceneAudio],
        demo_videos: dict[str, Path],
        srt_path: Path | None,
        output_dir: Path,
        build_dir: Path,
        dry_run: bool = False,
    ) -> Path:
        """Render the full video via Remotion.

        Args:
            plan: The VideoPlan.
            scene_audios: Voice-over audio per scene.
            demo_videos: Map of flow_name → video path.
            srt_path: Caption SRT for the primary language.
            output_dir: Where to write the final MP4s.
            build_dir: Where to write Remotion props JSON.
            dry_run: If True, skip the actual render.

        Returns:
            Path to the rendered captioned MP4.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        build_dir.mkdir(parents=True, exist_ok=True)

        # Build props JSON for Remotion
        props = self._build_props(plan, scene_audios, demo_videos, srt_path, output_dir)
        props_path = build_dir / "remotion_props.json"
        props_path.write_text(json.dumps(props, indent=2, default=str))
        logger.info("Remotion props written to %s", props_path)

        if dry_run:
            console.print("[yellow]--dry-run: skipping Remotion render[/yellow]")
            return output_dir / "video_captioned.mp4"

        # Install Remotion deps if needed
        self._ensure_remotion_deps()

        # Render clean (no captions)
        clean_out = output_dir / "video_clean.mp4"
        console.print("[cyan]Rendering clean video (no captions)...[/cyan]")
        self._run_remotion(
            props_path=props_path,
            output_path=clean_out,
            composition="VideoClean",
        )

        # Render with captions
        captioned_out = output_dir / "video_captioned.mp4"
        console.print("[cyan]Rendering captioned video...[/cyan]")
        self._run_remotion(
            props_path=props_path,
            output_path=captioned_out,
            composition="VideoCaptioned",
        )

        # Embed SRT as soft subtitle track
        if srt_path and srt_path.exists():
            self._embed_srt(captioned_out, srt_path, output_dir / "video_subtitled.mp4")

        # Generate contact sheet
        self._make_contact_sheet(captioned_out, output_dir / "contact_sheet.jpg")

        return captioned_out

    def _build_props(
        self,
        plan: VideoPlan,
        scene_audios: list[SceneAudio],
        demo_videos: dict[str, Path],
        srt_path: Path | None,
        output_dir: Path,
    ) -> dict:
        """Build the props object passed to Remotion."""
        audio_map = {a.scene_index: str(a.audio_path) for a in scene_audios}
        scenes_data = []

        for scene in plan.scenes:
            s = scene.model_dump()
            s["audio_path"] = audio_map.get(scene.index, "")
            s["duration_secs"] = next(
                (a.duration_secs for a in scene_audios if a.scene_index == scene.index),
                10.0,
            )
            if scene.demo_flow and scene.demo_flow in demo_videos:
                s["demo_video_path"] = str(demo_videos[scene.demo_flow])
            scenes_data.append(s)

        return {
            "plan": {
                "title": plan.title,
                "accent_color": plan.accent_color,
                "secondary_color": plan.secondary_color,
                "font_heading": plan.font_heading,
                "font_body": plan.font_body,
                "has_responsive_mobile": plan.has_responsive_mobile,
            },
            "scenes": scenes_data,
            "srt_path": str(srt_path) if srt_path else "",
            "width": self.render_cfg.width,
            "height": self.render_cfg.height,
            "fps": self.render_cfg.fps,
        }

    def _ensure_remotion_deps(self) -> None:
        """Install node_modules in the remotion directory if not present."""
        nm = self.remotion_dir / "node_modules"
        if not nm.exists():
            console.print("[cyan]Installing Remotion dependencies...[/cyan]")
            subprocess.run(
                ["npm", "install"],
                cwd=self.remotion_dir,
                check=True,
                capture_output=True,
            )

    def _run_remotion(
        self,
        props_path: Path,
        output_path: Path,
        composition: str,
    ) -> None:
        """Call `npx remotion render` for one composition."""
        cmd = [
            "npx", "remotion", "render",
            composition,
            str(output_path),
            "--props", str(props_path),
            "--concurrency", str(self.render_cfg.concurrency),
        ]
        if self.render_cfg.low_res_preview:
            cmd += ["--scale", "0.667"]

        logger.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            cwd=self.remotion_dir,
            capture_output=False,  # stream output to terminal
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Remotion render failed for composition '{composition}'. "
                f"Exit code: {result.returncode}"
            )
        logger.info("Rendered: %s", output_path)

    def _embed_srt(self, video_path: Path, srt_path: Path, output_path: Path) -> None:
        """Embed SRT as a soft subtitle track using ffmpeg."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(srt_path),
            "-c", "copy",
            "-c:s", "mov_text",
            "-metadata:s:s:0", "language=eng",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("SRT embedding failed: %s", result.stderr[:200])
        else:
            logger.info("SRT embedded: %s", output_path)

    def _make_contact_sheet(self, video_path: Path, output_path: Path) -> None:
        """Generate a contact sheet (one frame per 30 seconds)."""
        try:
            duration = _get_video_duration(video_path)
            n_frames = max(1, int(duration / 30))
            interval = duration / n_frames

            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vf", (
                    f"select='not(mod(t,{interval:.1f}))',scale=320:-1,tile={n_frames}x1"
                ),
                "-frames:v", "1",
                str(output_path),
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info("Contact sheet: %s", output_path)
        except Exception as e:
            logger.warning("Contact sheet generation failed: %s", e)


def _get_video_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-print_format", "json", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        return 480.0
