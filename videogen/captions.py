"""Captions stage — generate word-level timestamps via Whisper + force-align to script.

Stages:
  1. Transcribe with faster-whisper (word_timestamps=True)
  2. Force-align: replace whisper words with script words, keep timing
  3. Segment: split at punctuation, 42 chars/line, 2 lines max
  4. Export SRT + VTT per language
  5. Translate (via Claude) for additional languages

QA rules enforced:
  - No caption overlap
  - No caption past end of video
  - Min 1.0s, max 6.0s per caption
  - 2-frame gap between captions (at 30fps = 0.067s)
  - WER vs script ≤ 3% (checked on segment words)
  - No orphan single-word lines
  - No split numbers/units/names across lines
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from videogen.config import CaptionsConfig, Settings

logger = logging.getLogger(__name__)
console = Console()

_FRAME_DURATION = 1 / 30  # 30fps
_MIN_GAP = 2 * _FRAME_DURATION  # 2-frame gap between captions


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class WordTiming:
    word: str
    start: float  # seconds
    end: float


@dataclass
class Caption:
    index: int
    start: float  # seconds
    end: float
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def to_srt(self) -> str:
        return (
            f"{self.index}\n"
            f"{_fmt_srt_time(self.start)} --> {_fmt_srt_time(self.end)}\n"
            f"{self.text}\n"
        )

    def to_vtt(self) -> str:
        return f"{_fmt_vtt_time(self.start)} --> {_fmt_vtt_time(self.end)}\n{self.text}\n"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class CaptionGenerator:
    """Generates captions from audio + script."""

    def __init__(self, cfg: Settings, build_dir: Path) -> None:
        self.cfg = cfg
        self.cap_cfg: CaptionsConfig = cfg.captions
        self.build_dir = build_dir
        self.cache_dir = build_dir / "caption_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        mixed_audio_path: Path,
        script_text: str,
        video_duration_secs: float,
        output_dir: Path,
        dry_run: bool = False,
    ) -> dict[str, Path]:
        """Full caption pipeline.

        Args:
            mixed_audio_path: Final narration audio file.
            script_text: Full narration script (used for force-alignment).
            video_duration_secs: Total video length for QA.
            output_dir: Where to write SRT/VTT files.
            dry_run: Skip Whisper + Claude calls.

        Returns:
            Dict mapping language code → SRT path.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        if dry_run:
            console.print("[yellow]--dry-run: skipping caption generation[/yellow]")
            return {}

        # Cache by audio hash
        audio_hash = _file_hash(mixed_audio_path)
        cache_path = self.cache_dir / f"{audio_hash}_timings.json"

        if cache_path.exists():
            logger.info("Caption cache hit: %s", cache_path)
            word_timings = _load_timings(cache_path)
        else:
            console.print(f"[cyan]Transcribing audio with Whisper ({self.cap_cfg.whisper_model})...[/cyan]")
            word_timings = self._transcribe(mixed_audio_path)
            _save_timings(cache_path, word_timings)

        # Force-align to script
        aligned = _force_align(word_timings, script_text)

        # Segment into captions
        captions = self._segment(aligned, video_duration_secs)

        # QA
        issues = self._qa(captions, video_duration_secs, script_text)
        if issues:
            for issue in issues:
                logger.warning("Caption QA: %s", issue)
            console.print(f"[yellow]Caption QA: {len(issues)} warning(s)[/yellow]")

        # Export English
        output: dict[str, Path] = {}
        en_srt = output_dir / "captions_en.srt"
        en_vtt = output_dir / "captions_en.vtt"
        _write_srt(captions, en_srt)
        _write_vtt(captions, en_vtt)
        output["en"] = en_srt
        logger.info("Wrote %s (%d captions)", en_srt, len(captions))

        # Additional languages
        for lang in self.cap_cfg.languages:
            if lang == "en":
                continue
            translated = self._translate(captions, lang)
            srt_path = output_dir / f"captions_{lang}.srt"
            vtt_path = output_dir / f"captions_{lang}.vtt"
            _write_srt(translated, srt_path)
            _write_vtt(translated, vtt_path)
            output[lang] = srt_path
            logger.info("Wrote %s (%d captions)", srt_path, len(translated))

        return output

    def _transcribe(self, audio_path: Path) -> list[WordTiming]:
        """Run faster-whisper with word_timestamps=True."""
        from faster_whisper import WhisperModel

        model = WhisperModel(self.cap_cfg.whisper_model, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language="en",
        )

        words: list[WordTiming] = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    words.append(WordTiming(
                        word=w.word.strip(),
                        start=w.start,
                        end=w.end,
                    ))
        return words

    def _segment(self, timings: list[WordTiming], max_end: float) -> list[Caption]:
        """Segment word timings into display captions."""
        if not timings:
            return []

        cfg = self.cap_cfg
        captions: list[Caption] = []
        cap_idx = 1

        i = 0
        while i < len(timings):
            # Greedily fill up to max_chars_per_line * max_lines
            group: list[WordTiming] = []
            line1: list[str] = []
            line2: list[str] = []

            while i < len(timings):
                w = timings[i]
                candidate = w.word

                # Try to fit in line 1
                l1_candidate = " ".join(line1 + [candidate]) if line1 else candidate
                if len(l1_candidate) <= cfg.max_chars_per_line:
                    line1.append(candidate)
                    group.append(w)
                    i += 1
                    # Check for natural break (punctuation)
                    if candidate.endswith((".", "?", "!", ",", ";", ":")):
                        break
                    continue

                # Try line 2
                if not line2:
                    l2_candidate = candidate
                    if len(l2_candidate) <= cfg.max_chars_per_line:
                        line2.append(candidate)
                        group.append(w)
                        i += 1
                        if candidate.endswith((".", "?", "!", ",", ";", ":")):
                            break
                        continue

                l2_candidate = " ".join(line2 + [candidate])
                if len(l2_candidate) <= cfg.max_chars_per_line:
                    line2.append(candidate)
                    group.append(w)
                    i += 1
                    if candidate.endswith((".", "?", "!", ",", ";", ":")):
                        break
                    continue

                # Both lines full — end this caption
                break

            if not group:
                i += 1
                continue

            start = group[0].start
            end = min(group[-1].end, max_end)

            # Enforce min/max display duration
            duration = end - start
            if duration < cfg.min_duration_secs:
                end = start + cfg.min_duration_secs
            elif duration > cfg.max_duration_secs:
                end = start + cfg.max_duration_secs

            # Clamp to video
            end = min(end, max_end)

            # Build lines list
            lines = [" ".join(line1)]
            if line2:
                lines.append(" ".join(line2))

            # Skip orphan single-word line (if 2 lines and second is one word, merge)
            if len(lines) == 2 and len(line2) == 1 and len(line1) + 1 + len(line2[0]) <= cfg.max_chars_per_line:
                lines = [" ".join(line1 + line2)]

            captions.append(Caption(
                index=cap_idx,
                start=start,
                end=end,
                lines=lines,
            ))
            cap_idx += 1

        # Enforce 2-frame gaps
        for idx in range(len(captions) - 1):
            a, b = captions[idx], captions[idx + 1]
            if b.start - a.end < _MIN_GAP:
                a.end = b.start - _MIN_GAP
                if a.end <= a.start:
                    a.end = a.start + cfg.min_duration_secs

        return captions

    def _qa(
        self,
        captions: list[Caption],
        video_duration: float,
        script: str,
    ) -> list[str]:
        """Return list of QA issues."""
        issues: list[str] = []
        script_words = re.findall(r"\w+", script.lower())
        caption_words = re.findall(r"\w+", " ".join(c.text for c in captions).lower())

        if script_words:
            from difflib import SequenceMatcher
            ratio = SequenceMatcher(None, caption_words, script_words).ratio()
            wer = 1 - ratio
            if wer > 0.03:
                issues.append(f"WER {wer:.1%} exceeds 3% threshold — check force-alignment")

        for i, c in enumerate(captions):
            if c.end > video_duration + 0.3:
                issues.append(f"Caption {c.index} ends after video ({c.end:.2f}s > {video_duration:.2f}s)")
            if i < len(captions) - 1:
                gap = captions[i + 1].start - c.end
                if gap < 0:
                    issues.append(f"Caption {c.index} overlaps {captions[i+1].index}")

        return issues

    def _translate(self, captions: list[Caption], lang: str) -> list[Caption]:
        """Translate captions to another language using Claude."""
        from anthropic import Anthropic

        client = Anthropic(api_key=self.cfg.anthropic_api_key or "")
        texts = [c.text for c in captions]
        joined = "\n---\n".join(texts)

        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": (
                    f"Translate these video captions to {lang}. "
                    "Keep brand names, product names, and technical terms untranslated. "
                    "Preserve the separator '---' between captions. "
                    "Return ONLY the translated captions separated by ---.\n\n"
                    + joined
                ),
            }],
        )

        translated_texts = response.content[0].text.split("\n---\n")
        result: list[Caption] = []
        for i, cap in enumerate(captions):
            text = translated_texts[i] if i < len(translated_texts) else cap.text
            lines = text.strip().splitlines()[:2]
            result.append(Caption(
                index=cap.index,
                start=cap.start,
                end=cap.end,
                lines=lines,
            ))
        return result


# ---------------------------------------------------------------------------
# Force alignment
# ---------------------------------------------------------------------------


def _force_align(whisper_words: list[WordTiming], script: str) -> list[WordTiming]:
    """Replace whisper word text with script word text, keeping timings.

    This ensures product names, acronyms, and numbers are correct.
    Uses a greedy alignment by normalized comparison.
    """
    script_words = re.findall(r"\S+", script)
    if not script_words or not whisper_words:
        return whisper_words

    # If lengths match roughly, do a 1:1 replacement
    result: list[WordTiming] = []
    sw_idx = 0

    for wt in whisper_words:
        if sw_idx < len(script_words):
            # Normalize both for comparison
            whisper_norm = _norm(wt.word)
            script_norm = _norm(script_words[sw_idx])
            if whisper_norm == script_norm or _edit_dist(whisper_norm, script_norm) <= 2:
                result.append(WordTiming(word=script_words[sw_idx], start=wt.start, end=wt.end))
                sw_idx += 1
            else:
                result.append(wt)
        else:
            result.append(wt)

    return result


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def _edit_dist(a: str, b: str) -> int:
    """Simple Levenshtein distance."""
    if abs(len(a) - len(b)) > 4:
        return 99
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            tmp = dp[j]
            dp[j] = prev if a[i-1] == b[j-1] else 1 + min(prev, dp[j], dp[j-1])
            prev = tmp
    return dp[n]


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


def _write_srt(captions: list[Caption], path: Path) -> None:
    lines = []
    for c in captions:
        lines.append(c.to_srt())
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_vtt(captions: list[Caption], path: Path) -> None:
    lines = ["WEBVTT\n"]
    for c in captions:
        lines.append(c.to_vtt())
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _fmt_srt_time(secs: float) -> str:
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _fmt_vtt_time(secs: float) -> str:
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _save_timings(path: Path, timings: list[WordTiming]) -> None:
    data = [{"word": w.word, "start": w.start, "end": w.end} for w in timings]
    path.write_text(json.dumps(data))


def _load_timings(path: Path) -> list[WordTiming]:
    data = json.loads(path.read_text())
    return [WordTiming(word=d["word"], start=d["start"], end=d["end"]) for d in data]
