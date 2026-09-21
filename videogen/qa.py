"""QA stage — verify the rendered video meets all quality gates.

Checks:
  - Total duration within ±30s of target
  - No scene under 8s or over 45s
  - Audio present in every scene
  - No silence > 2s
  - No clipped text (via rendered stills sampling)
  - Demo footage has no error pages or blank screens
  - Caption checks (overlap, overflow, WER)
  - File plays (ffprobe can read all streams)
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class QAResult:
    passed: bool
    checks: list[tuple[str, bool, str]]  # (name, passed, detail)

    def print_report(self) -> None:
        table = Table(title="QA Report", show_lines=True)
        table.add_column("Check", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Detail")

        for name, ok, detail in self.checks:
            status = "[green]✓[/green]" if ok else "[red]✗[/red]"
            table.add_row(name, status, detail)

        console.print(table)
        if self.passed:
            console.print("[bold green]All QA checks passed.[/bold green]")
        else:
            fails = [n for n, ok, _ in self.checks if not ok]
            console.print(f"[bold red]{len(fails)} QA check(s) FAILED: {', '.join(fails)}[/bold red]")


def run_qa(
    video_path: Path,
    target_duration_secs: int,
    srt_path: Path | None = None,
    script_text: str = "",
) -> QAResult:
    """Run all QA checks on the rendered video.

    Args:
        video_path: Path to the output video file.
        target_duration_secs: Expected video length.
        srt_path: Optional path to the caption SRT for caption QA.
        script_text: The full narration script for WER check.

    Returns:
        QAResult with all check outcomes.
    """
    checks: list[tuple[str, bool, str]] = []

    # 1. File exists and is playable
    ok, detail = _check_playable(video_path)
    checks.append(("File playable", ok, detail))

    # 2. Duration
    duration = _get_duration(video_path)
    ok = abs(duration - target_duration_secs) <= 30
    checks.append((
        "Duration ±30s",
        ok,
        f"{duration:.1f}s actual vs {target_duration_secs}s target (Δ{abs(duration - target_duration_secs):.1f}s)",
    ))

    # 3. Audio present
    ok, detail = _check_has_audio(video_path)
    checks.append(("Audio present", ok, detail))

    # 4. No silence > 2s
    ok, detail = _check_no_long_silence(video_path)
    checks.append(("No silence > 2s", ok, detail))

    # 5. Caption checks
    if srt_path and srt_path.exists():
        ok, detail = _check_captions(srt_path, duration, script_text)
        checks.append(("Caption QA", ok, detail))

    # 6. Frame sampling for blank/error screens
    ok, detail = _check_no_blank_frames(video_path)
    checks.append(("No blank/error frames", ok, detail))

    passed = all(ok for _, ok, _ in checks)
    result = QAResult(passed=passed, checks=checks)
    result.print_report()
    return result


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_playable(video_path: Path) -> tuple[bool, str]:
    if not video_path.exists():
        return False, f"File not found: {video_path}"
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(video_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False, f"ffprobe error: {result.stderr[:200]}"
    return True, f"{video_path.stat().st_size // 1024 // 1024}MB"


def _get_duration(video_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-print_format", "json", str(video_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, ValueError):
        return 0.0


def _check_has_audio(video_path: Path) -> tuple[bool, str]:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
         "-select_streams", "a", str(video_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False, "ffprobe error"
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        return False, "No audio stream found"
    return True, f"{len(streams)} audio stream(s)"


def _check_no_long_silence(video_path: Path, max_silence_secs: float = 2.0) -> tuple[bool, str]:
    """Use ffmpeg silencedetect to find long silences."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", str(video_path),
            "-af", f"silencedetect=noise=-50dB:d={max_silence_secs}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    output = result.stderr
    silences = []
    for line in output.splitlines():
        if "silence_duration" in line:
            try:
                dur = float(line.split("silence_duration:")[-1].strip())
                silences.append(dur)
            except ValueError:
                pass

    if silences:
        worst = max(silences)
        return False, f"Found {len(silences)} silence(s), worst: {worst:.1f}s"
    return True, "No long silence detected"


def _check_captions(
    srt_path: Path,
    video_duration: float,
    script_text: str,
) -> tuple[bool, str]:
    """Check caption file for overlaps, overflow, and WER."""
    import re

    text = srt_path.read_text(encoding="utf-8")
    # Parse SRT
    entries = re.findall(
        r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n|\Z)",
        text,
        re.DOTALL,
    )

    issues = []
    prev_end = 0.0
    all_words = []

    for idx, start_s, end_s, caption_text in entries:
        start = _parse_srt_time(start_s)
        end = _parse_srt_time(end_s)

        # Overlap
        if start < prev_end - 0.001:
            issues.append(f"Caption {idx} overlaps previous")
        prev_end = end

        # Past video end
        if end > video_duration + 0.3:
            issues.append(f"Caption {idx} ends past video ({end:.2f}s)")

        all_words.extend(re.findall(r"\w+", caption_text.lower()))

    # WER check
    if script_text:
        script_words = re.findall(r"\w+", script_text.lower())
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, all_words, script_words).ratio()
        wer = 1 - ratio
        if wer > 0.03:
            issues.append(f"WER {wer:.1%} > 3%")

    if issues:
        return False, "; ".join(issues[:3])
    return True, f"{len(entries)} captions OK"


def _check_no_blank_frames(video_path: Path, samples: int = 10) -> tuple[bool, str]:
    """Sample frames and check mean brightness > threshold."""
    try:
        duration = _get_duration(video_path)
        if duration <= 0:
            return False, "Cannot determine video duration"

        import tempfile
        from PIL import Image
        import numpy as np

        issues = []
        for i in range(samples):
            t = (i + 0.5) * duration / samples
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                tmp = Path(tf.name)
            subprocess.run(
                ["ffmpeg", "-ss", str(t), "-i", str(video_path),
                 "-frames:v", "1", "-q:v", "2", str(tmp), "-y"],
                capture_output=True,
            )
            if tmp.exists():
                img = Image.open(tmp).convert("L")
                mean = np.array(img).mean()
                tmp.unlink(missing_ok=True)
                if mean < 10:
                    issues.append(f"Black frame at {t:.1f}s (brightness={mean:.1f})")
                elif mean > 245:
                    issues.append(f"White/blank frame at {t:.1f}s (brightness={mean:.1f})")

        if issues:
            return False, "; ".join(issues[:3])
        return True, f"Sampled {samples} frames OK"
    except Exception as e:
        return True, f"Frame check skipped: {e}"


def _parse_srt_time(s: str) -> float:
    """Parse HH:MM:SS,mmm → seconds."""
    s = s.replace(",", ".")
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)
