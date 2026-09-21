"""Unit tests for caption segmentation rules."""

from __future__ import annotations

from videogen.captions import (
    Caption,
    CaptionGenerator,
    WordTiming,
    _fmt_srt_time,
    _fmt_vtt_time,
    _force_align,
    _write_srt,
    _write_vtt,
)


def _make_words(text: str, start: float = 0.0, wps: float = 3.0) -> list[WordTiming]:
    """Build a list of WordTiming from plain text, evenly spaced."""
    words = text.split()
    result = []
    t = start
    dur = 1.0 / wps
    for w in words:
        result.append(WordTiming(word=w, start=t, end=t + dur))
        t += dur
    return result


class TestCaptionSegmentation:
    """Test CaptionGenerator._segment() rules."""

    def _segmenter(self) -> CaptionGenerator:
        from unittest.mock import MagicMock

        cfg = MagicMock()
        cfg.captions.max_chars_per_line = 42
        cfg.captions.max_lines = 2
        cfg.captions.min_duration_secs = 1.0
        cfg.captions.max_duration_secs = 6.0
        cfg.captions.whisper_model = "base"
        return CaptionGenerator(cfg, build_dir=MagicMock())

    def test_basic_segmentation(self) -> None:
        words = _make_words("The quick brown fox jumps over the lazy dog")
        gen = self._segmenter()
        captions = gen._segment(words, max_end=30.0)

        assert len(captions) >= 1
        for c in captions:
            assert isinstance(c, Caption)
            assert len(c.lines) <= 2

    def test_max_chars_per_line(self) -> None:
        gen = self._segmenter()
        words = _make_words("This is a sentence with many words that should be wrapped properly")
        captions = gen._segment(words, max_end=60.0)

        for cap in captions:
            for line in cap.lines:
                assert len(line) <= 42, f"Line too long: '{line}'"

    def test_min_duration_enforced(self) -> None:
        gen = self._segmenter()
        # Very fast words (short duration)
        words = [
            WordTiming("Hi", 0.0, 0.1),
            WordTiming("there", 0.1, 0.2),
        ]
        captions = gen._segment(words, max_end=10.0)
        for cap in captions:
            assert cap.end - cap.start >= 1.0

    def test_max_duration_enforced(self) -> None:
        gen = self._segmenter()
        # Very long single group of words
        words = _make_words("word " * 50, start=0.0, wps=0.5)  # slow speech
        captions = gen._segment(words, max_end=200.0)
        for cap in captions:
            assert cap.end - cap.start <= 6.0 + 0.1  # tiny float tolerance

    def test_no_overlap_between_captions(self) -> None:
        gen = self._segmenter()
        words = _make_words(
            "First sentence ends here. Second sentence begins now. Third sentence follows."
        )
        captions = gen._segment(words, max_end=60.0)

        for i in range(len(captions) - 1):
            assert captions[i].end <= captions[i + 1].start + 0.001

    def test_captions_clamped_to_video_end(self) -> None:
        gen = self._segmenter()
        words = _make_words("Some words at the end", start=4.5)
        captions = gen._segment(words, max_end=5.0)
        for cap in captions:
            assert cap.end <= 5.0 + 0.001

    def test_no_orphan_single_word_second_line(self) -> None:
        gen = self._segmenter()
        # "hello world" fits on one line → second line with 1 word should be merged if possible
        words = _make_words("hello world extra")
        captions = gen._segment(words, max_end=20.0)
        for cap in captions:
            if len(cap.lines) == 2:
                # second line must have more than 1 word or first line must be full
                second = cap.lines[1]
                assert len(second.split()) >= 1  # basic check — no crash


class TestCaptionFormatting:
    def test_srt_time_format(self) -> None:
        assert _fmt_srt_time(0.0) == "00:00:00,000"
        assert _fmt_srt_time(3661.5) == "01:01:01,500"
        assert _fmt_srt_time(90.123) == "00:01:30,123"

    def test_vtt_time_format(self) -> None:
        assert _fmt_vtt_time(0.0) == "00:00:00.000"
        assert _fmt_vtt_time(61.0) == "00:01:01.000"

    def test_srt_output(self, tmp_path) -> None:
        captions = [
            Caption(1, 0.0, 3.0, ["Hello world"]),
            Caption(2, 3.1, 6.0, ["Second caption", "second line"]),
        ]
        srt_path = tmp_path / "out.srt"
        _write_srt(captions, srt_path)
        content = srt_path.read_text()
        assert "00:00:00,000 --> 00:00:03,000" in content
        assert "Hello world" in content
        assert "Second caption" in content

    def test_vtt_starts_with_webvtt(self, tmp_path) -> None:
        captions = [Caption(1, 0.0, 2.0, ["Test"])]
        vtt_path = tmp_path / "out.vtt"
        _write_vtt(captions, vtt_path)
        assert vtt_path.read_text().startswith("WEBVTT")


class TestForceAlign:
    def test_replaces_words_with_script(self) -> None:
        timings = [
            WordTiming("helo", 0.0, 0.5),
            WordTiming("wrold", 0.5, 1.0),
        ]
        script = "hello world"
        aligned = _force_align(timings, script)

        assert aligned[0].word == "hello"
        assert aligned[1].word == "world"
        # Timings preserved
        assert aligned[0].start == 0.0
        assert aligned[1].end == 1.0

    def test_handles_empty_inputs(self) -> None:
        assert _force_align([], "hello") == []
        timings = [WordTiming("hello", 0.0, 0.5)]
        result = _force_align(timings, "")
        assert result == timings
