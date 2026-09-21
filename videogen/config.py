"""Configuration model for videogen.

Loaded from a YAML file (--config) and env vars (VIDEOGEN_* prefix).
Validated at startup with actionable error messages.
Secrets come only from env — never from YAML, never logged.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console

_console = Console(stderr=True)

# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class InputConfig(BaseModel):
    pptx: Path = Field(..., description="Path to the .pptx file")
    repo: str = Field(..., description="Git repo URL or local path")
    live_url: str | None = None
    logo: Path | None = None
    brand_colors: list[str] = Field(default_factory=list, description="Hex colors from brand")
    target_length_secs: int = Field(default=480, ge=60, le=1800, description="Target video length (seconds)")
    demo_credentials: dict[str, str] = Field(default_factory=dict, description="Login/seed credentials for demo")
    background_music: Path | None = None

    @field_validator("pptx")
    @classmethod
    def pptx_must_exist(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"PPTX file not found: {v}")
        if v.suffix.lower() != ".pptx":
            raise ValueError(f"Expected a .pptx file, got: {v.suffix}")
        return v

    @field_validator("brand_colors", mode="before")
    @classmethod
    def normalize_colors(cls, v: list[str]) -> list[str]:
        return [c if c.startswith("#") else f"#{c}" for c in v]


class VoiceConfig(BaseModel):
    provider: Literal["elevenlabs", "edge_tts", "auto"] = "auto"
    voice_id: str = "Rachel"  # ElevenLabs voice name or Edge TTS voice
    model: str = "eleven_turbo_v2"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class CaptionsConfig(BaseModel):
    languages: list[str] = Field(default_factory=lambda: ["en"])
    burn_in: bool = True
    word_highlight: bool = True
    clean_mode: bool = False
    max_chars_per_line: int = 42
    max_lines: int = 2
    min_duration_secs: float = 1.0
    max_duration_secs: float = 6.0
    font_size_px: int = 44
    whisper_model: str = "base"

    @field_validator("languages", mode="before")
    @classmethod
    def normalize_langs(cls, v: list[str]) -> list[str]:
        return [lang.lower().strip() for lang in v]


class RenderConfig(BaseModel):
    width: int = 1920
    height: int = 1080
    fps: int = 30
    concurrency: int = Field(default=4, ge=1, le=16)
    codec: str = "h264"
    crf: int = Field(default=18, ge=0, le=51)
    audio_target_lufs: float = -16.0
    output_dir: Path = Path("out")
    build_dir: Path = Path("build")
    low_res_preview: bool = False  # 1280x720 for quick preview


class DemoConfig(BaseModel):
    max_flows: int = Field(default=5, ge=1, le=10)
    flow_min_secs: int = 30
    flow_max_secs: int = 60
    total_min_secs: int = 120
    total_max_secs: int = 180
    cursor_visible: bool = True
    mask_sensitive: bool = True
    retry_flaky_steps: int = 3
    speedramp_threshold_secs: float = 2.0
    speedramp_factor: float = 3.0


class LLMConfig(BaseModel):
    model: str = "claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.3


# ---------------------------------------------------------------------------
# Root settings (reads from YAML + env)
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VIDEOGEN_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    input: InputConfig | None = None
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    captions: CaptionsConfig = Field(default_factory=CaptionsConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
    demo: DemoConfig = Field(default_factory=DemoConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)

    # Secrets — from env only
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")

    model_config = SettingsConfigDict(
        env_prefix="VIDEOGEN_",
        env_nested_delimiter="__",
        populate_by_name=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def pull_secrets_from_env(self) -> "Settings":
        """Override: secrets come directly from standard env var names."""
        if self.anthropic_api_key is None:
            self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        if self.elevenlabs_api_key is None:
            self.elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
        return self

    @model_validator(mode="after")
    def voice_provider_auto(self) -> "Settings":
        """If provider='auto', pick based on available API key."""
        if self.voice.provider == "auto":
            if self.elevenlabs_api_key:
                self.voice.provider = "elevenlabs"
            else:
                self.voice.provider = "edge_tts"
        return self

    def validate_for_build(self) -> None:
        """Hard-fail with actionable messages if required things are missing."""
        errors: list[str] = []

        if self.input is None:
            errors.append("'input' section is required in config. Set input.pptx and input.repo.")

        if not self.anthropic_api_key:
            errors.append(
                "ANTHROPIC_API_KEY not set. Export it: export ANTHROPIC_API_KEY=sk-ant-..."
            )

        if self.voice.provider == "elevenlabs" and not self.elevenlabs_api_key:
            errors.append(
                "ELEVENLABS_API_KEY not set but voice.provider=elevenlabs. "
                "Either set the key or remove it from config to fall back to edge_tts."
            )

        # Check system dependencies
        missing_bins = _check_binaries(
            ["ffmpeg", "ffprobe", "node", "npm", "libreoffice", "pdftoppm", "git"]
        )
        for b in missing_bins:
            errors.append(
                f"Required binary not found: {b}. "
                + {
                    "ffmpeg": "Install: brew install ffmpeg  or  apt install ffmpeg",
                    "ffprobe": "Comes with ffmpeg",
                    "node": "Install: https://nodejs.org",
                    "npm": "Comes with Node.js",
                    "libreoffice": "Install: brew install libreoffice  or  apt install libreoffice",
                    "pdftoppm": "Install: brew install poppler  or  apt install poppler-utils",
                    "git": "Install: brew install git  or  apt install git",
                }.get(b, "Install via your package manager")
            )

        if errors:
            _console.print("[bold red]Configuration errors:[/bold red]")
            for e in errors:
                _console.print(f"  [red]•[/red] {e}")
            raise SystemExit(1)


def _check_binaries(names: list[str]) -> list[str]:
    """Return names of binaries not found on PATH."""
    import shutil

    return [n for n in names if shutil.which(n) is None]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(config_path: Path | None = None) -> Settings:
    """Load settings from YAML file (if given) merged with env vars."""
    data: dict = {}
    if config_path and config_path.exists():
        with config_path.open() as f:
            data = yaml.safe_load(f) or {}

    # Resolve relative paths relative to config file location
    if config_path and "input" in data:
        base = config_path.parent
        for key in ("pptx", "logo", "background_music"):
            if key in data["input"] and data["input"][key]:
                p = Path(data["input"][key])
                if not p.is_absolute():
                    data["input"][key] = str(base / p)

    return Settings(**data)
