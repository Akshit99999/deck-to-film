"""Story planner — uses Claude to generate the scene plan and demo script.

Produces build/plan.json, which is the single source of truth for all
downstream stages. The plan can be hand-edited and re-rendered without
re-running this stage (idempotent by hash of inputs).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, Field, field_validator
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from tenacity import retry, stop_after_attempt, wait_exponential

from videogen.config import LLMConfig, Settings
from videogen.ingest.pptx_parser import ParsedDeck
from videogen.ingest.repo_analyzer import RepoAnalysis

logger = logging.getLogger(__name__)
console = Console()

# ---------------------------------------------------------------------------
# Plan schema
# ---------------------------------------------------------------------------

SceneType = Literal[
    "title", "bullets", "stat", "slide_showcase", "live_demo",
    "architecture", "outro", "custom"
]

TransitionType = Literal["crossfade", "wipe", "camera_push", "dissolve"]


class DemoStep(BaseModel):
    """A single step in the live demo recording script."""

    action: Literal["goto", "click", "type", "scroll", "hover", "wait", "press", "screenshot"]
    target: str = Field(..., description="Accessible selector: role/text/label or CSS")
    value: str | None = None
    narration_cue: str = Field(..., description="The narration sentence this step accompanies")
    wait_after_ms: int = 500

    @field_validator("target")
    @classmethod
    def target_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("target must not be empty")
        return v


class DemoFlow(BaseModel):
    """A 30-60s user flow in the live demo."""

    name: str
    description: str
    steps: list[DemoStep]
    estimated_secs: int = Field(ge=20, le=120)
    start_url: str = "/"


class Scene(BaseModel):
    """One scene in the video."""

    index: int
    type: SceneType
    heading: str = Field(..., max_length=60)
    bullets: list[str] = Field(default_factory=list, max_length=4)
    narration: str = Field(..., description="Full narration text for this scene")
    assets: list[str] = Field(default_factory=list, description="Slide PNG paths or other assets")
    motif_3d: str = Field(default="floating_panels", description="Three.js motif identifier")
    accent_color: str = Field(default="#6366f1", description="Hex accent for this scene")
    transition_in: TransitionType = "crossfade"
    demo_flow: str | None = None  # name of DemoFlow to play (live_demo scenes only)
    stat_value: str | None = None  # for stat scenes
    stat_label: str | None = None

    @field_validator("bullets", mode="before")
    @classmethod
    def trim_bullets(cls, v: list[str]) -> list[str]:
        return [b[:80] for b in v[:4]]

    @field_validator("narration")
    @classmethod
    def narration_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("narration must not be empty")
        return v


class VideoPlan(BaseModel):
    """The complete video plan — serialized to build/plan.json."""

    version: str = "1.0"
    title: str
    total_target_secs: int
    accent_color: str
    secondary_color: str
    font_heading: str
    font_body: str
    scenes: list[Scene]
    demo_flows: list[DemoFlow]
    narration_wpm: int = 150
    voice_id: str
    has_responsive_mobile: bool = False

    @field_validator("scenes")
    @classmethod
    def at_least_one_scene(cls, v: list[Scene]) -> list[Scene]:
        if not v:
            raise ValueError("Plan must have at least one scene")
        return v


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM = """You are an expert product video director and scriptwriter.
You receive a parsed PowerPoint deck and a repository analysis.
Your job is to produce a structured JSON scene plan for an ~8-minute explainer video.

STRICT RULES:
1. Never invent facts not present in the deck or repo. No made-up metrics, customers, features.
2. If a fact is missing (e.g. user count), omit it entirely.
3. Narration is conversational, ~150 words/minute. Write numbers as words when spoken.
4. No technical jargon unless the audience is clearly technical.
5. Demo flows cover only features that EXIST in the repo code.
6. Respond ONLY with a single JSON object matching the VideoPlan schema.
7. Each bullet is ≤9 words. Heading is ≤8 words.
"""

_USER_TEMPLATE = """
## Deck Content
{deck_text}

## Repository Analysis
{repo_json}

## Configuration
- Target length: {target_secs} seconds ({target_mins:.1f} minutes)
- Voice: {voice_id}
- Brand colors: {brand_colors}
- Available demo credentials: {demo_creds}

## Required output format (JSON)
Return a JSON object matching this schema:

{{
  "version": "1.0",
  "title": "string",
  "total_target_secs": {target_secs},
  "accent_color": "#hex",
  "secondary_color": "#hex",
  "font_heading": "string (Google Fonts name)",
  "font_body": "string (Google Fonts name)",
  "narration_wpm": 150,
  "voice_id": "{voice_id}",
  "has_responsive_mobile": true|false,
  "scenes": [
    {{
      "index": 1,
      "type": "title|bullets|stat|slide_showcase|live_demo|architecture|outro",
      "heading": "≤8 words",
      "bullets": ["≤9 words each", "max 4"],
      "narration": "Full spoken text for this scene",
      "assets": ["slide_001.png"],
      "motif_3d": "floating_panels|orbit_sphere|data_flow|device_frame|graph_nodes|counter_ring",
      "accent_color": "#hex",
      "transition_in": "crossfade|wipe|camera_push|dissolve",
      "demo_flow": "flow name or null",
      "stat_value": "42%" or null,
      "stat_label": "Conversion Rate" or null
    }}
  ],
  "demo_flows": [
    {{
      "name": "short-slug",
      "description": "What this flow shows",
      "estimated_secs": 45,
      "start_url": "/",
      "steps": [
        {{
          "action": "goto|click|type|scroll|hover|wait|press",
          "target": "role=button[name='Sign in'] or #element-id",
          "value": "text to type or null",
          "narration_cue": "The sentence being spoken during this step",
          "wait_after_ms": 500
        }}
      ]
    }}
  ]
}}

Narrative structure (in order):
1. Title scene (~15s)
2. Hook / Problem (~30s)
3. Solution intro + slides (~60s)
4. Key features - 2-3 bullet scenes (~120s total)
5. LIVE DEMO scene(s) — 2-3 flows, ~120-180s total
6. How it works — architecture overview, visual only, no code (~45s)
7. Impact / traction (only if evidence in deck, else skip)
8. Roadmap (only if in deck)
9. Call to action / Outro (~20s)

Return ONLY the JSON. No markdown, no explanation.
"""

_CRITIC_SYSTEM = """You are a video script quality reviewer.
You receive a scene plan JSON and the original sources.
Check for:
1. Factual drift — any claim not supported by deck or repo
2. Pacing — scenes < 8s or > 45s of narration
3. Repetition — same point made in multiple scenes
4. Demo feasibility — steps targeting elements unlikely to exist
5. Total duration vs target (±30s is acceptable)
Return the CORRECTED JSON (same schema). Fix issues, don't just flag them.
Return ONLY the corrected JSON.
"""

# ---------------------------------------------------------------------------
# Main planner
# ---------------------------------------------------------------------------


class Planner:
    """Generates the video plan using Claude."""

    def __init__(self, cfg: Settings) -> None:
        self.cfg = cfg
        self.llm = LLMConfig() if cfg.llm is None else cfg.llm
        self._client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)

    def plan(
        self,
        deck: ParsedDeck,
        analysis: RepoAnalysis,
        output_dir: Path,
        dry_run: bool = False,
    ) -> VideoPlan:
        """Generate the scene plan. Caches by input hash.

        Args:
            deck: Parsed PPTX content.
            analysis: Repo analysis.
            output_dir: Where to write plan.json.
            dry_run: If True, show cost estimate but do not call the API.

        Returns:
            VideoPlan instance.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_path = output_dir / "plan.json"

        # Cache key = hash of deck + repo analysis
        cache_key = _hash_inputs(deck.full_text, json.dumps(analysis.to_dict()))
        cache_meta_path = output_dir / "plan_meta.json"

        if plan_path.exists() and cache_meta_path.exists():
            meta = json.loads(cache_meta_path.read_text())
            if meta.get("cache_key") == cache_key:
                logger.info("Plan cache hit — loading %s", plan_path)
                return VideoPlan.model_validate_json(plan_path.read_text())

        target_secs = self.cfg.input.target_length_secs if self.cfg.input else 480
        brand_colors = (self.cfg.input.brand_colors if self.cfg.input else []) or ["#6366f1"]
        demo_creds = (
            list(self.cfg.input.demo_credentials.keys()) if self.cfg.input else []
        )

        user_prompt = _USER_TEMPLATE.format(
            deck_text=deck.full_text[:12000],
            repo_json=json.dumps(analysis.to_dict(), indent=2),
            target_secs=target_secs,
            target_mins=target_secs / 60,
            voice_id=self.cfg.voice.voice_id,
            brand_colors=", ".join(brand_colors),
            demo_creds=", ".join(demo_creds) if demo_creds else "none provided",
        )

        # Cost estimate
        input_tokens = _estimate_tokens(user_prompt)
        estimated_cost = (input_tokens / 1_000_000) * 15.0  # Claude Opus pricing ~$15/M input
        console.print(
            f"[cyan]Plan generation estimate:[/cyan] ~{input_tokens:,} tokens, "
            f"~${estimated_cost:.3f} (two passes)"
        )

        if dry_run:
            console.print("[yellow]--dry-run set, skipping API call[/yellow]")
            return _dummy_plan(target_secs, self.cfg.voice.voice_id)

        # First pass
        console.print("[cyan]Generating scene plan (pass 1/2)...[/cyan]")
        raw_json = self._call_claude(
            system=_SYSTEM,
            user=user_prompt,
            max_tokens=self.llm.max_tokens,
        )
        plan = _parse_plan_json(raw_json)

        # Critic pass
        console.print("[cyan]Running critic pass (pass 2/2)...[/cyan]")
        critic_prompt = (
            f"ORIGINAL SOURCES:\n{deck.full_text[:6000]}\n\n"
            f"PLAN:\n{json.dumps(plan.model_dump(), indent=2)}"
        )
        raw_json2 = self._call_claude(
            system=_CRITIC_SYSTEM,
            user=critic_prompt,
            max_tokens=self.llm.max_tokens,
        )
        plan = _parse_plan_json(raw_json2)

        # Write plan
        plan_path.write_text(plan.model_dump_json(indent=2))
        cache_meta_path.write_text(json.dumps({"cache_key": cache_key}))
        logger.info("Plan written to %s (%d scenes)", plan_path, len(plan.scenes))
        return plan

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    def _call_claude(self, system: str, user: str, max_tokens: int) -> str:
        """Call Claude API with retry and return raw response text."""
        response = self._client.messages.create(
            model=self.llm.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_plan_json(raw: str) -> VideoPlan:
    """Extract and parse JSON from LLM response."""
    # Strip markdown code fences if present
    clean = re.sub(r"```(?:json)?\n?([\s\S]*?)\n?```", r"\1", raw).strip()
    if not clean.startswith("{"):
        # Find first { ... }
        m = re.search(r"\{[\s\S]+\}", clean)
        if not m:
            raise ValueError(f"No JSON found in LLM response: {clean[:200]}")
        clean = m.group(0)
    data: dict[str, Any] = json.loads(clean)
    return VideoPlan.model_validate(data)


def _hash_inputs(*parts: str) -> str:
    combined = "\n".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _dummy_plan(target_secs: int, voice_id: str) -> VideoPlan:
    """Return a minimal stub plan for --dry-run."""
    return VideoPlan(
        title="DRY RUN PLAN",
        total_target_secs=target_secs,
        accent_color="#6366f1",
        secondary_color="#818cf8",
        font_heading="Inter",
        font_body="Inter",
        voice_id=voice_id,
        scenes=[
            Scene(
                index=1,
                type="title",
                heading="DRY RUN — no API call",
                narration="This is a dry run. No API call was made.",
                motif_3d="floating_panels",
                accent_color="#6366f1",
                transition_in="crossfade",
            )
        ],
        demo_flows=[],
    )
