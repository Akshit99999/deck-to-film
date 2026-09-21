"""Voice-over generation — ElevenLabs primary, Edge TTS fallback.

Features:
  - Per-scene audio generation with retry + exponential backoff
  - Cache by SHA-256(text + voice + model) — only re-generates on change
  - ffprobe-measured real durations
  - Loudness normalization to target LUFS
  - Optional music ducking
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import tempfile
from pathlib import Path

import edge_tts
from pydub import AudioSegment
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from tenacity import retry, stop_after_attempt, wait_exponential

from videogen.config import Settings, VoiceConfig
from videogen.planner import Scene, VideoPlan

logger = logging.getLogger(__name__)
console = Console()


@dataclass_style := {}  # just a placeholder import trick — use dataclasses below
from dataclasses import dataclass


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
        """Generate audio for every scene in the plan.

        Returns list of SceneAudio, one per scene.
        """
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
        cache_key = _audio_cache_key(scene.narration, self.voice_cfg.voice_id, self.voice_cfg.model)
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

        logger.info("Generating voice for scene %d: %.50s...", scene.index, scene.narration)

        if self.voice_cfg.provider == "elevenlabs":
            raw = self._generate_elevenlabs(scene.narration)
        else:
            raw = asyncio.run(self._generate_edge_tts(scene.narration))

        # Loudness normalize
        normalized = _normalize_loudness(raw, target_lufs=-16.0)
        normalized.export(str(out_path), format="mp3", bitrate="192k")

        duration = _measure_duration(out_path)
        return SceneAudio(
            scene_index=scene.index,
            audio_path=out_path,
            duration_secs=duration,
            text=scene.narration,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_elevenlabs(self, text: str) -> AudioSegment:
        """Generate audio via ElevenLabs API."""
        from elevenlabs import generate, set_api_key, Voice, VoiceSettings

        set_api_key(self.cfg.elevenlabs_api_key or "")

        audio_bytes: bytes = generate(  # type: ignore[assignment]
            text=text,
            voice=Voice(
                voice_id=self.voice_cfg.voice_id,
                settings=VoiceSettings(stability=0.5, similarity_boost=0.75),
            ),
            model=self.voice_cfg.model,
        )

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = Path(f.name)

        seg = AudioSegment.from_mp3(str(tmp_path))
        tmp_path.unlink(missing_ok=True)
        return seg

    async def _generate_edge_tts(self, text: str) -> AudioSegment:
        """Generate audio via Edge TTS (free, no API key needed)."""
        voice_name = _map_edge_tts_voice(self.voice_cfg.voice_id)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = Path(f.name)

        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(str(tmp_path))

        seg = AudioSegment.from_mp3(str(tmp_path))
        tmp_path.unlink(missing_ok=True)
        return seg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _audio_cache_key(text: str, voice_id: str, model: str) -> str:
    data = f"{text}|{voice_id}|{model}"
    return hashlib.sha256(data.encode()).hexdigest()[:12]


def _measure_duration(path: Path) -> float:
    """Return audio duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", str(path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {result.stderr}")
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            return float(stream.get("duration", 0))
    return 0.0


def _normalize_loudness(audio: AudioSegment, target_lufs: float = -16.0) -> AudioSegment:
    """Normalize audio to target LUFS using pyloudnorm."""
    try:
        import numpy as np
        import pyloudnorm as pyln

        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        samples /= 2 ** (audio.sample_width * 8 - 1)
        if audio.channels == 2:
            samples = samples.reshape(-1, 2)

        meter = pyln.Meter(audio.frame_rate)
        loudness = meter.integrated_loudness(samples)

        if abs(loudness - target_lufs) < 0.5:
            return audio  # already close enough

        gain_db = target_lufs - loudness
        return audio + gain_db

    except Exception as e:
        logger.warning("Loudness normalization failed (%s), returning original", e)
        return audio


def _map_edge_tts_voice(voice_id: str) -> str:
    """Map a friendly voice name to an Edge TTS voice string."""
    mapping = {
        "Rachel": "en-US-AriaNeural",
        "Josh": "en-US-GuyNeural",
        "Adam": "en-US-DavisNeural",
        "Sam": "en-US-JasonNeural",
        "Bella": "en-US-JennyNeural",
        "Antoni": "en-US-TonyNeural",
    }
    return mapping.get(voice_id, "en-US-AriaNeural")
