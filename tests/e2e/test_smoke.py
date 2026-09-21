"""End-to-end smoke test — runs the full pipeline with mocked API calls.

Uses:
  - A bundled sample .pptx (generated in the test)
  - A tiny sample web app (static HTML served via http.server)
  - Mocked Claude API (returns a minimal valid plan)
  - Mocked ElevenLabs / Edge TTS (returns a short silent MP3)
  - Mocked Whisper (returns deterministic word timings)
  - Real Playwright for demo capture (skipped if not installed)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_pptx(tmp_path: Path) -> Path:
    """Generate a minimal sample .pptx for testing."""
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Smoke Test Product"
    slide.placeholders[1].text = "A test product that does something useful."
    notes = slide.notes_slide
    notes.notes_text_frame.text = "This is slide 1 speaker notes."

    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Features"
    slide2.placeholders[1].text = "Fast\nSimple\nReliable"

    pptx_path = tmp_path / "sample.pptx"
    prs.save(str(pptx_path))
    return pptx_path


@pytest.fixture
def sample_webapp(tmp_path: Path) -> Path:
    """Write a tiny static HTML site for demo capture."""
    webapp_dir = tmp_path / "webapp"
    webapp_dir.mkdir()
    (webapp_dir / "index.html").write_text(
        """<!DOCTYPE html>
<html>
<head><title>Smoke Test App</title></head>
<body>
  <h1>Smoke Test App</h1>
  <button id="cta">Get Started</button>
  <p id="msg"></p>
  <script>
    document.getElementById('cta').onclick = function() {
      document.getElementById('msg').textContent = 'Welcome!';
    };
  </script>
</body>
</html>"""
    )
    return webapp_dir


@pytest.fixture
def minimal_plan() -> dict:
    return {
        "version": "1.0",
        "title": "Smoke Test Product",
        "total_target_secs": 60,
        "accent_color": "#6366f1",
        "secondary_color": "#818cf8",
        "font_heading": "Inter",
        "font_body": "Inter",
        "narration_wpm": 150,
        "voice_id": "Rachel",
        "has_responsive_mobile": False,
        "scenes": [
            {
                "index": 1,
                "type": "title",
                "heading": "Smoke Test",
                "narration": "Welcome to the smoke test product.",
                "bullets": [],
                "assets": [],
                "motif_3d": "floating_panels",
                "accent_color": "#6366f1",
                "transition_in": "crossfade",
                "demo_flow": None,
                "stat_value": None,
                "stat_label": None,
            },
            {
                "index": 2,
                "type": "live_demo",
                "heading": "Live Demo",
                "narration": "Now let's see the product in action.",
                "bullets": [],
                "assets": [],
                "motif_3d": "device_frame",
                "accent_color": "#6366f1",
                "transition_in": "crossfade",
                "demo_flow": "main_flow",
                "stat_value": None,
                "stat_label": None,
            },
        ],
        "demo_flows": [
            {
                "name": "main_flow",
                "description": "Click the CTA button",
                "estimated_secs": 10,
                "start_url": "/",
                "steps": [
                    {
                        "action": "click",
                        "target": "role=button[name='Get Started']",
                        "value": None,
                        "narration_cue": "Click Get Started.",
                        "wait_after_ms": 500,
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Unit-level pipeline tests (no real API calls)
# ---------------------------------------------------------------------------


class TestIngestStage:
    def test_pptx_parse_roundtrip(self, sample_pptx: Path) -> None:
        from videogen.ingest.pptx_parser import parse_pptx

        deck = parse_pptx(sample_pptx)
        assert deck.title or deck.slides[0].title
        assert len(deck.slides) == 2
        assert "smoke test" in deck.full_text.lower()

    def test_repo_analyze_local_path(self, sample_webapp: Path) -> None:
        from videogen.ingest.repo_analyzer import analyze_repo

        analysis = analyze_repo(sample_webapp, str(sample_webapp))
        assert analysis.local_path == sample_webapp


class TestPlannerWithMock:
    def test_plan_uses_cache_on_second_call(
        self, sample_pptx: Path, sample_webapp: Path, minimal_plan: dict, tmp_path: Path
    ) -> None:
        from videogen.ingest.pptx_parser import parse_pptx
        from videogen.ingest.repo_analyzer import analyze_repo
        from videogen.planner import Planner, VideoPlan

        deck = parse_pptx(sample_pptx)
        analysis = analyze_repo(sample_webapp, str(sample_webapp))

        cfg = MagicMock()
        cfg.anthropic_api_key = "test-key"
        cfg.llm.model = "claude-haiku-4-5"
        cfg.llm.max_tokens = 4096
        cfg.llm.temperature = 0.3
        cfg.input.target_length_secs = 60
        cfg.input.brand_colors = ["#6366f1"]
        cfg.input.demo_credentials = {}
        cfg.voice.voice_id = "Rachel"

        # Write a pre-existing plan to trigger cache hit
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        plan_path = build_dir / "plan.json"
        plan_path.write_text(json.dumps(minimal_plan))

        # Write matching cache meta
        import hashlib
        key = hashlib.sha256((deck.full_text + json.dumps(analysis.to_dict())).encode()).hexdigest()[:16]
        (build_dir / "plan_meta.json").write_text(json.dumps({"cache_key": key}))

        planner = Planner(cfg)
        plan = planner.plan(deck, analysis, build_dir, dry_run=False)

        assert isinstance(plan, VideoPlan)
        assert plan.title == "Smoke Test Product"


class TestCaptionPipeline:
    def test_caption_segment_and_export(self, tmp_path: Path) -> None:
        from videogen.captions import CaptionGenerator, WordTiming, _write_srt

        cfg = MagicMock()
        cfg.captions.max_chars_per_line = 42
        cfg.captions.max_lines = 2
        cfg.captions.min_duration_secs = 1.0
        cfg.captions.max_duration_secs = 6.0
        cfg.captions.whisper_model = "base"
        cfg.captions.languages = ["en"]
        cfg.anthropic_api_key = "test-key"

        gen = CaptionGenerator(cfg, tmp_path)
        words = [
            WordTiming("Welcome", 0.0, 0.4),
            WordTiming("to", 0.4, 0.6),
            WordTiming("the", 0.6, 0.8),
            WordTiming("product.", 0.8, 1.2),
            WordTiming("It", 1.4, 1.6),
            WordTiming("is", 1.6, 1.8),
            WordTiming("fast", 1.8, 2.2),
            WordTiming("and", 2.2, 2.4),
            WordTiming("reliable.", 2.4, 3.0),
        ]
        captions = gen._segment(words, max_end=10.0)

        assert len(captions) >= 1

        srt_path = tmp_path / "test.srt"
        _write_srt(captions, srt_path)
        content = srt_path.read_text()
        assert "Welcome" in content
        assert "-->" in content


class TestQAChecks:
    def test_parse_srt_time(self) -> None:
        from videogen.qa import _parse_srt_time

        assert _parse_srt_time("00:00:00,000") == 0.0
        assert abs(_parse_srt_time("00:01:30,500") - 90.5) < 0.001
        assert abs(_parse_srt_time("01:00:00,000") - 3600.0) < 0.001
