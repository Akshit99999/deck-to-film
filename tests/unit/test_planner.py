"""Unit tests for VideoPlan schema validation and duration math."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from videogen.planner import (
    DemoFlow,
    DemoStep,
    Scene,
    VideoPlan,
    _estimate_tokens,
    _parse_plan_json,
)


class TestSceneValidation:
    def test_valid_scene(self) -> None:
        s = Scene(
            index=1,
            type="title",
            heading="Hello World",
            narration="Welcome to our product.",
            motif_3d="floating_panels",
            accent_color="#6366f1",
            transition_in="crossfade",
        )
        assert s.heading == "Hello World"

    def test_narration_required(self) -> None:
        with pytest.raises(ValidationError):
            Scene(
                index=1,
                type="title",
                heading="Hello",
                narration="",  # empty → error
                motif_3d="floating_panels",
                accent_color="#6366f1",
                transition_in="crossfade",
            )

    def test_bullets_capped_at_4(self) -> None:
        s = Scene(
            index=1,
            type="bullets",
            heading="Features",
            narration="Here are our features.",
            bullets=["A", "B", "C", "D", "E", "F"],  # 6 → trimmed to 4
            motif_3d="floating_panels",
            accent_color="#6366f1",
            transition_in="crossfade",
        )
        assert len(s.bullets) == 4

    def test_heading_max_length(self) -> None:
        # 60 chars is the heading limit
        long_heading = "A" * 61
        with pytest.raises(ValidationError):
            Scene(
                index=1,
                type="title",
                heading=long_heading,
                narration="Test",
                motif_3d="floating_panels",
                accent_color="#6366f1",
                transition_in="crossfade",
            )


class TestDemoStepValidation:
    def test_valid_step(self) -> None:
        step = DemoStep(
            action="click",
            target="role=button[name='Sign in']",
            narration_cue="Click sign in.",
        )
        assert step.action == "click"

    def test_empty_target_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DemoStep(action="click", target="", narration_cue="Cue")


class TestVideoPlanValidation:
    def _minimal_plan(self) -> dict:
        return {
            "version": "1.0",
            "title": "Test Product",
            "total_target_secs": 480,
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
                    "heading": "Hello",
                    "narration": "Welcome.",
                    "bullets": [],
                    "assets": [],
                    "motif_3d": "floating_panels",
                    "accent_color": "#6366f1",
                    "transition_in": "crossfade",
                    "demo_flow": None,
                    "stat_value": None,
                    "stat_label": None,
                }
            ],
            "demo_flows": [],
        }

    def test_valid_plan(self) -> None:
        plan = VideoPlan.model_validate(self._minimal_plan())
        assert plan.title == "Test Product"
        assert len(plan.scenes) == 1

    def test_empty_scenes_rejected(self) -> None:
        data = self._minimal_plan()
        data["scenes"] = []
        with pytest.raises(ValidationError):
            VideoPlan.model_validate(data)

    def test_parse_plan_json_strips_fences(self) -> None:
        data = self._minimal_plan()
        raw = "```json\n" + json.dumps(data) + "\n```"
        plan = _parse_plan_json(raw)
        assert plan.title == "Test Product"

    def test_parse_plan_json_plain(self) -> None:
        data = self._minimal_plan()
        plan = _parse_plan_json(json.dumps(data))
        assert len(plan.scenes) == 1


class TestDurationMath:
    def test_estimate_tokens(self) -> None:
        # 400 chars ≈ 100 tokens
        text = "a" * 400
        assert _estimate_tokens(text) == 100

    def test_narration_word_count(self) -> None:
        # 150 wpm * 8 min = 1200 words maximum for full video
        narration = " ".join(["word"] * 1200)
        wpm = 150
        expected_secs = (1200 / wpm) * 60
        assert abs(expected_secs - 480) < 1
