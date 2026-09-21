"""videogen CLI — entry point for all pipeline stages.

Usage:
  videogen build       # full pipeline
  videogen plan        # ingest + story planning only  → build/plan.json
  videogen demo        # demo capture only
  videogen voice       # voice-over generation only
  videogen captions    # caption generation only
  videogen render      # rendering only (needs plan.json)
  videogen preview     # low-res render for quick review
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from videogen.config import load_config
from videogen.pipeline import Pipeline

console = Console()

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]videogen[/bold cyan] — PPTX + repo → polished explainer video",
            border_style="cyan",
        )
    )


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=False, path_type=Path),
    default=Path("videogen.yaml"),
    show_default=True,
    help="Path to YAML config file.",
)
@click.option("--dry-run", is_flag=True, default=False, help="Print cost estimate, do not run.")
@click.pass_context
def app(ctx: click.Context, config_path: Path, dry_run: bool) -> None:
    """Turn a PowerPoint deck + website repo into a narrated explainer video."""
    _banner()
    ctx.ensure_object(dict)
    cfg = load_config(config_path if config_path.exists() else None)
    ctx.obj["cfg"] = cfg
    ctx.obj["dry_run"] = dry_run


@app.command()
@click.pass_context
def build(ctx: click.Context) -> None:
    """Run the full pipeline end-to-end."""
    cfg = ctx.obj["cfg"]
    dry_run = ctx.obj["dry_run"]
    cfg.validate_for_build()
    pipeline = Pipeline(cfg, dry_run=dry_run)
    pipeline.run_all()


@app.command()
@click.pass_context
def plan(ctx: click.Context) -> None:
    """Ingest PPTX + repo and generate the scene plan (build/plan.json)."""
    cfg = ctx.obj["cfg"]
    dry_run = ctx.obj["dry_run"]
    cfg.validate_for_build()
    pipeline = Pipeline(cfg, dry_run=dry_run)
    pipeline.run_plan()


@app.command()
@click.pass_context
def demo(ctx: click.Context) -> None:
    """Capture the live website demo footage."""
    cfg = ctx.obj["cfg"]
    dry_run = ctx.obj["dry_run"]
    cfg.validate_for_build()
    pipeline = Pipeline(cfg, dry_run=dry_run)
    pipeline.run_demo()


@app.command()
@click.pass_context
def voice(ctx: click.Context) -> None:
    """Generate voice-over audio for each scene."""
    cfg = ctx.obj["cfg"]
    dry_run = ctx.obj["dry_run"]
    cfg.validate_for_build()
    pipeline = Pipeline(cfg, dry_run=dry_run)
    pipeline.run_voice()


@app.command()
@click.pass_context
def captions(ctx: click.Context) -> None:
    """Generate and align captions (SRT/VTT)."""
    cfg = ctx.obj["cfg"]
    dry_run = ctx.obj["dry_run"]
    cfg.validate_for_build()
    pipeline = Pipeline(cfg, dry_run=dry_run)
    pipeline.run_captions()


@app.command()
@click.pass_context
def render(ctx: click.Context) -> None:
    """Render the final video from plan.json and all assets."""
    cfg = ctx.obj["cfg"]
    dry_run = ctx.obj["dry_run"]
    cfg.validate_for_build()
    pipeline = Pipeline(cfg, dry_run=dry_run)
    pipeline.run_render()


@app.command()
@click.pass_context
def preview(ctx: click.Context) -> None:
    """Render a low-resolution preview (1280×720) for quick review."""
    cfg = ctx.obj["cfg"]
    dry_run = ctx.obj["dry_run"]
    cfg.validate_for_build()
    # Force low-res for preview
    cfg.render.low_res_preview = True
    cfg.render.width = 1280
    cfg.render.height = 720
    pipeline = Pipeline(cfg, dry_run=dry_run)
    pipeline.run_render()


if __name__ == "__main__":
    app()
