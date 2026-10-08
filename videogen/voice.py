"""Voice-over generation — ElevenLabs primary, Edge TTS fallback.

Features:
  - Per-scene audio generation with retry + exponential backoff
  - Cache by SHA-256(text + voice + model) — only re-generates on change
  - ffprobe-measured real durations
  - Loudness normalization to target LUFS
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import edge_tts
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from tenacity import retry, stop_after_attempt, wait_exponential

from videogen.config import Settings, VoiceConfig
from videogen.planner import Scene, VideoPlan

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class SceneAudio:
    scene_index: int
    audio_path: Path
    duration_secs: float
    text: str


class VoiceGenerator:
    """Generates voice-over audio for each scene."""

    def __init__(self, cfg: Settings, output_dir: Path) -> None:
        self.cfg = cfg
        self.voice_cfg: VoiceConfig = cfg.voice
        self.output_dir = output_dir / "voice"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_all(self, plan: VideoPlan, dry_run: bool = False) -> list[SceneAudio]:
        """Generate audio for every scene in the plan."""
        total_chars = sum(len(s.narration) for s in plan.scenes)
        console.print(
            f"[cyan]Voice generation:[/cyan] {len(plan.scenes)} scenes, "
            f"{total_chars:,} chars, provider={self.voice_cfg.provider}"
        )
        if dry_run:
            console.print("[yellow]--dry-run: skipping voice generation[/yellow]")
            return []

        results: list[SceneAudio] = []
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
            task = prog.add_task("Generating voice-over...", total=len(plan.scenes))
            for scene in plan.scenes:
                audio = self._generate_scene(scene)
                results.append(audio)
                prog.advance(task)

        return results

    def _generate_scene(self, scene: Scene) -> SceneAudio:
        """Generate audio for one scene, with caching."""
        # Multi-voice: use scene.voice_id if given, or alternate across 3 voices (1 female, 2 male)
        if scene.voice_id:
            voice_id = scene.voice_id
        else:
            voice_rotation = ["Rachel", "Josh", "Adam"]
            voice_id = voice_rotation[(scene.index - 1) % len(voice_rotation)]

        cache_key = _audio_cache_key(scene.narration, voice_id, self.voice_cfg.model)
        out_path = self.output_dir / f"scene_{scene.index:03d}_{cache_key}.mp3"

        if out_path.exists():
            duration = _measure_duration(out_path)
            logger.debug("Voice cache hit: scene %d (%.1fs)", scene.index, duration)
            return SceneAudio(
                scene_index=scene.index,
                audio_path=out_path,
                duration_secs=duration,
                text=scene.narration,
            )

        logger.info("Generating voice for scene %d using [%s]: %.50s...", scene.index, voice_id, scene.narration)

        if self.voice_cfg.provider == "elevenlabs":
            raw_path = self._generate_elevenlabs(scene.narration, voice_id=voice_id)
        else:
            raw_path = asyncio.run(self._generate_edge_tts(scene.narration, voice_id=voice_id))

        # Loudness normalize via ffmpeg (no pydub dependency)
        _normalize_loudness_ffmpeg(raw_path, out_path, target_lufs=-16.0)
        raw_path.unlink(missing_ok=True)

        duration = _measure_duration(out_path)
        return SceneAudio(
            scene_index=scene.index,
            audio_path=out_path,
            duration_secs=duration,
            text=scene.narration,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_elevenlabs(self, text: str, voice_id: str | None = None) -> Path:
        """Generate audio via ElevenLabs API. Returns temp MP3 path."""
        from elevenlabs import generate, set_api_key, Voice, VoiceSettings

        target_voice = voice_id or self.voice_cfg.voice_id
        set_api_key(self.cfg.elevenlabs_api_key or "")
        audio_bytes: bytes = generate(  # type: ignore[assignment]
            text=text,
            voice=Voice(
                voice_id=target_voice,
                settings=VoiceSettings(stability=0.5, similarity_boost=0.75),
            ),
            model=self.voice_cfg.model,
        )
        tmp = Path(tempfile.mktemp(suffix=".mp3"))
        tmp.write_bytes(audio_bytes)
        return tmp

    async def _generate_edge_tts(self, text: str, voice_id: str | None = None) -> Path:
        """Generate audio via Edge TTS (free, no API key needed)."""
        target_voice = voice_id or self.voice_cfg.voice_id
        voice_name = _map_edge_tts_voice(target_voice)
        tmp = Path(tempfile.mktemp(suffix=".mp3"))
        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(str(tmp))
        return tmp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _audio_cache_key(text: str, voice_id: str, model: str) -> str:
    data = f"{text}|{voice_id}|{model}"
    return hashlib.sha256(data.encode()).hexdigest()[:12]


def _measure_duration(path: Path) -> float:
    """Return audio duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            return float(stream.get("duration", 0))
    return 0.0


def _normalize_loudness_ffmpeg(src: Path, dst: Path, target_lufs: float = -16.0) -> None:
    """Normalize audio loudness using ffmpeg loudnorm filter."""
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src),
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
            "-ar", "44100", "-ac", "2",
            str(dst),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.warning("Loudness normalization failed, copying as-is: %s", result.stderr[:200])
        import shutil
        shutil.copy2(src, dst)


def _map_edge_tts_voice(voice_id: str) -> str:
    """Map a friendly voice name to an Edge TTS voice string."""
    mapping = {
        "Rachel": "en-US-AriaNeural",          # Female (Expressive, clear)
        "Bella": "en-US-JennyNeural",          # Female
        "Josh": "en-US-GuyNeural",             # Male 1 (Energetic, crisp)
        "Sam": "en-US-JasonNeural",            # Male
        "Adam": "en-US-ChristopherNeural",     # Male 2 (Deep, authoritative)
        "Antoni": "en-US-TonyNeural",          # Male
        "en-US-AriaNeural": "en-US-AriaNeural",
        "en-US-GuyNeural": "en-US-GuyNeural",
        "en-US-ChristopherNeural": "en-US-ChristopherNeural",
    }
    return mapping.get(voice_id, "en-US-AriaNeural")
