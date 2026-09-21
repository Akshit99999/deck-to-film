"""Pipeline orchestrator — runs all stages in order, caches each one.

Stages:
  1. Ingest (PPTX parse + repo clone/analyze)
  2. Plan (Claude → scene plan + demo script)
  3. Demo capture (Playwright)
  4. Voice-over generation
  5. Caption generation
  6. Render (Remotion)
  7. QA
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rich.console import Console

from videogen.captions import CaptionGenerator
from videogen.config import Settings
from videogen.demo.capture import DemoCapture
from videogen.demo.runner import run_site
from videogen.ingest.pptx_parser import ParsedDeck, parse_pptx, render_slides_to_png
from videogen.ingest.repo_analyzer import RepoAnalysis, analyze_repo, clone_repo
from videogen.planner import Planner, VideoPlan
from videogen.qa import run_qa
from videogen.renderer import Renderer
from videogen.voice import SceneAudio, VoiceGenerator

logger = logging.getLogger(__name__)
console = Console()


class Pipeline:
    """Runs the full videogen pipeline."""

    def __init__(self, cfg: Settings, dry_run: bool = False) -> None:
        self.cfg = cfg
        self.dry_run = dry_run

        # Resolve directories
        assert cfg.input is not None, "Input config required"
        self.build_dir = cfg.render.build_dir
        self.output_dir = cfg.render.output_dir
        self.remotion_dir = Path(__file__).parent.parent / "remotion"

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%H:%M:%S",
        )

    # ------------------------------------------------------------------
    # Stage runners
    # ------------------------------------------------------------------

    def run_all(self) -> None:
        """Run all stages end-to-end."""
        deck, analysis = self._stage_ingest()
        plan = self._stage_plan(deck, analysis)
        demo_videos = self._stage_demo(plan, analysis)
        scene_audios = self._stage_voice(plan)
        srt_paths = self._stage_captions(plan, scene_audios)
        srt_en = srt_paths.get("en")
        video_path = self._stage_render(plan, scene_audios, demo_videos, srt_en)
        self._stage_qa(video_path, plan, srt_en, plan)

        console.print(f"\n[bold green]✓ Done! Output files in {self.output_dir}/[/bold green]")
        self._print_summary(video_path)

    def run_plan(self) -> VideoPlan:
        deck, analysis = self._stage_ingest()
        return self._stage_plan(deck, analysis)

    def run_demo(self) -> dict[str, Path]:
        deck, analysis = self._stage_ingest()
        plan = self._stage_plan(deck, analysis)
        return self._stage_demo(plan, analysis)

    def run_voice(self) -> list[SceneAudio]:
        plan = self._load_plan()
        return self._stage_voice(plan)

    def run_captions(self) -> dict[str, Path]:
        plan = self._load_plan()
        scene_audios = self._stage_voice(plan)
        return self._stage_captions(plan, scene_audios)

    def run_render(self) -> Path:
        plan = self._load_plan()
        scene_audios = self._stage_voice(plan)
        demo_videos = self._load_demo_videos(plan)
        srt_paths = self._stage_captions(plan, scene_audios)
        srt_en = srt_paths.get("en")
        return self._stage_render(plan, scene_audios, demo_videos, srt_en)

    # ------------------------------------------------------------------
    # Individual stages
    # ------------------------------------------------------------------

    def _stage_ingest(self) -> tuple[ParsedDeck, RepoAnalysis]:
        console.rule("[bold]Stage 1: Ingest[/bold]")
        cfg = self.cfg.input
        assert cfg is not None

        # Parse PPTX
        deck = parse_pptx(cfg.pptx)

        # Render slide PNGs
        slides_dir = self.build_dir / "slides"
        render_slides_to_png(deck, slides_dir)

        # Clone + analyze repo
        repo_path = clone_repo(cfg.repo, self.build_dir / "repo")
        analysis = analyze_repo(repo_path, cfg.repo)

        # Write analysis for debugging
        analysis_path = self.build_dir / "repo_analysis.json"
        self.build_dir.mkdir(parents=True, exist_ok=True)
        analysis_path.write_text(json.dumps(analysis.to_dict(), indent=2))
        logger.info("Repo analysis written to %s", analysis_path)

        return deck, analysis

    def _stage_plan(self, deck: ParsedDeck, analysis: RepoAnalysis) -> VideoPlan:
        console.rule("[bold]Stage 2: Plan[/bold]")
        planner = Planner(self.cfg)
        return planner.plan(deck, analysis, self.build_dir, dry_run=self.dry_run)

    def _stage_demo(self, plan: VideoPlan, analysis: RepoAnalysis) -> dict[str, Path]:
        console.rule("[bold]Stage 3: Demo Capture[/bold]")
        if not plan.demo_flows:
            console.print("[yellow]No demo flows in plan — skipping demo capture.[/yellow]")
            return {}

        cfg_input = self.cfg.input
        assert cfg_input is not None
        demo_dir = self.build_dir / "demo"
        demo_dir.mkdir(parents=True, exist_ok=True)

        capture = DemoCapture(output_dir=demo_dir, mask_sensitive=self.cfg.demo.mask_sensitive)
        demo_videos: dict[str, Path] = {}

        live_url = cfg_input.live_url
        demo_creds = dict(cfg_input.demo_credentials) if cfg_input.demo_credentials else {}

        with run_site(analysis, env_overrides=demo_creds, live_url=live_url) as base_url:
            for flow in plan.demo_flows:
                console.print(f"[cyan]Capturing flow: {flow.name}[/cyan]")
                result = capture.capture_flow_sync(flow, base_url)
                if result.video_path.exists():
                    demo_videos[flow.name] = result.video_path
                    console.print(
                        f"[green]✓ {flow.name}: {result.duration_ms/1000:.1f}s[/green]"
                    )
                else:
                    console.print(f"[red]✗ {flow.name}: capture failed[/red]")

        # Write demo script JSON
        demo_script_path = demo_dir / "demo_script.json"
        demo_script_path.write_text(
            json.dumps([f.model_dump() for f in plan.demo_flows], indent=2)
        )
        return demo_videos

    def _stage_voice(self, plan: VideoPlan) -> list[SceneAudio]:
        console.rule("[bold]Stage 4: Voice-Over[/bold]")
        gen = VoiceGenerator(self.cfg, self.output_dir)
        return gen.generate_all(plan, dry_run=self.dry_run)

    def _stage_captions(
        self,
        plan: VideoPlan,
        scene_audios: list[SceneAudio],
    ) -> dict[str, Path]:
        console.rule("[bold]Stage 5: Captions[/bold]")

        if not scene_audios:
            console.print("[yellow]No audio — skipping captions.[/yellow]")
            return {}

        # Mix all scene narrations into a single audio file for Whisper
        mixed_path = self.build_dir / "mixed_narration.mp3"
        if not mixed_path.exists() or self.dry_run:
            _mix_audio_files([a.audio_path for a in scene_audios], mixed_path)

        full_script = "\n ".join(a.text for a in scene_audios)
        total_duration = sum(a.duration_secs for a in scene_audios)

        gen = CaptionGenerator(self.cfg, self.build_dir)
        return gen.generate(
            mixed_audio_path=mixed_path,
            script_text=full_script,
            video_duration_secs=total_duration,
            output_dir=self.output_dir,
            dry_run=self.dry_run,
        )

    def _stage_render(
        self,
        plan: VideoPlan,
        scene_audios: list[SceneAudio],
        demo_videos: dict[str, Path],
        srt_path: Path | None,
    ) -> Path:
        console.rule("[bold]Stage 6: Render[/bold]")
        renderer = Renderer(self.cfg, self.remotion_dir)
        return renderer.render(
            plan=plan,
            scene_audios=scene_audios,
            demo_videos=demo_videos,
            srt_path=srt_path,
            output_dir=self.output_dir,
            build_dir=self.build_dir,
            dry_run=self.dry_run,
        )

    def _stage_qa(
        self,
        video_path: Path,
        plan: VideoPlan,
        srt_path: Path | None,
        plan_obj: VideoPlan,
    ) -> None:
        console.rule("[bold]Stage 7: QA[/bold]")
        if self.dry_run or not video_path.exists():
            console.print("[yellow]Skipping QA (dry-run or video not found)[/yellow]")
            return

        script_text = " ".join(s.narration for s in plan_obj.scenes)
        result = run_qa(
            video_path=video_path,
            target_duration_secs=plan.total_target_secs,
            srt_path=srt_path,
            script_text=script_text,
        )
        if not result.passed:
            console.print(
                "[bold red]QA failed — review the issues above before distributing.[/bold red]"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_plan(self) -> VideoPlan:
        plan_path = self.build_dir / "plan.json"
        if not plan_path.exists():
            raise FileNotFoundError(
                f"build/plan.json not found. Run `videogen plan` first."
            )
        return VideoPlan.model_validate_json(plan_path.read_text())

    def _load_demo_videos(self, plan: VideoPlan) -> dict[str, Path]:
        demo_dir = self.build_dir / "demo"
        result: dict[str, Path] = {}
        if not demo_dir.exists():
            return result
        for flow in plan.demo_flows:
            matches = list(demo_dir.glob(f"{flow.name}_*.webm"))
            if matches:
                result[flow.name] = max(matches, key=lambda p: p.stat().st_mtime)
        return result

    def _print_summary(self, video_path: Path) -> None:
        console.print("\n[bold]Output files:[/bold]")
        for f in sorted(self.output_dir.glob("*")):
            size_mb = f.stat().st_size / 1024 / 1024
            console.print(f"  {f.name:40s} {size_mb:.1f}MB")


def _mix_audio_files(paths: list[Path], output: Path) -> None:
    """Concatenate audio files into one using ffmpeg concat."""
    import tempfile

    if not paths:
        return

    list_file = Path(tempfile.mktemp(suffix=".txt"))
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in paths if p.exists()))

    import subprocess
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    list_file.unlink(missing_ok=True)
