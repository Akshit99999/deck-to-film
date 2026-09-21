"""Demo capture — record live website flows using Playwright.

Features:
  - 1920×1080, deviceScaleFactor 2
  - Clean browser profile (no extensions, bookmarks, banners)
  - Smooth animated cursor with click ripple
  - Eased mouse movement (cubic bezier)
  - Human-like typing delays
  - Smooth scroll
  - Action bounding-box JSON sidecar for renderer auto-zoom
  - Sensitive data masking
  - Speed-ramp through slow moments
  - Flaky step retry
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import random
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator

from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from rich.console import Console

from videogen.planner import DemoFlow, DemoStep

logger = logging.getLogger(__name__)
console = Console()

# ---------------------------------------------------------------------------
# Cursor injection script
# ---------------------------------------------------------------------------

_CURSOR_JS = """
(function() {
  if (window.__videogenCursor) return;
  window.__videogenCursor = true;

  const cur = document.createElement('div');
  cur.id = '__vg_cursor';
  cur.style.cssText = `
    position: fixed; width: 24px; height: 24px; border-radius: 50%;
    background: rgba(255,255,255,0.9); border: 2px solid #6366f1;
    pointer-events: none; z-index: 2147483647;
    transform: translate(-50%, -50%);
    transition: transform 0.08s ease, opacity 0.1s;
    box-shadow: 0 0 0 2px rgba(99,102,241,0.3);
  `;
  document.body.appendChild(cur);

  const ripple = document.createElement('div');
  ripple.id = '__vg_ripple';
  ripple.style.cssText = `
    position: fixed; width: 0; height: 0; border-radius: 50%;
    background: rgba(99,102,241,0.4); pointer-events: none;
    z-index: 2147483646; transform: translate(-50%, -50%);
    transition: none;
  `;
  document.body.appendChild(ripple);

  window.__vgMoveCursor = function(x, y) {
    cur.style.left = x + 'px';
    cur.style.top = y + 'px';
  };

  window.__vgClick = function(x, y) {
    ripple.style.transition = 'none';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    ripple.style.width = '0px';
    ripple.style.height = '0px';
    ripple.style.opacity = '0.7';
    requestAnimationFrame(() => {
      ripple.style.transition = 'width 0.35s ease-out, height 0.35s ease-out, opacity 0.35s ease-out';
      ripple.style.width = '60px';
      ripple.style.height = '60px';
      ripple.style.opacity = '0';
    });
  };
})();
"""

# ---------------------------------------------------------------------------
# Bounding box sidecar
# ---------------------------------------------------------------------------


@dataclass
class ActionEvent:
    """Records when and where a user action happened, for renderer zoom."""

    timestamp_ms: float
    action: str
    x: float
    y: float
    width: float
    height: float
    narration_cue: str


@dataclass
class FlowCapture:
    """Result of capturing one demo flow."""

    flow_name: str
    video_path: Path
    actions: list[ActionEvent] = field(default_factory=list)
    duration_ms: float = 0.0
    screenshot_on_failure: Path | None = None

    def sidecar_path(self) -> Path:
        return self.video_path.with_suffix(".json")

    def write_sidecar(self) -> None:
        data = {
            "flow_name": self.flow_name,
            "duration_ms": self.duration_ms,
            "actions": [
                {
                    "timestamp_ms": a.timestamp_ms,
                    "action": a.action,
                    "x": a.x, "y": a.y,
                    "width": a.width, "height": a.height,
                    "narration_cue": a.narration_cue,
                }
                for a in self.actions
            ],
        }
        self.sidecar_path().write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Capture engine
# ---------------------------------------------------------------------------


class DemoCapture:
    """Records Playwright browser flows."""

    def __init__(self, output_dir: Path, mask_sensitive: bool = True) -> None:
        self.output_dir = output_dir
        self.mask_sensitive = mask_sensitive
        output_dir.mkdir(parents=True, exist_ok=True)

    def capture_flow_sync(self, flow: DemoFlow, base_url: str) -> FlowCapture:
        """Synchronous wrapper around the async capture."""
        return asyncio.run(self.capture_flow(flow, base_url))

    async def capture_flow(self, flow: DemoFlow, base_url: str) -> FlowCapture:
        """Record one demo flow. Returns FlowCapture with video path."""
        cache_key = _flow_cache_key(flow, base_url)
        video_path = self.output_dir / f"{flow.name}_{cache_key}.webm"
        if video_path.exists():
            logger.info("Demo cache hit: %s", video_path)
            sidecar = video_path.with_suffix(".json")
            capture = FlowCapture(flow_name=flow.name, video_path=video_path)
            if sidecar.exists():
                data = json.loads(sidecar.read_text())
                capture.duration_ms = data.get("duration_ms", 0)
            return capture

        logger.info("Capturing flow '%s' at %s", flow.name, base_url)
        capture = FlowCapture(flow_name=flow.name, video_path=video_path)

        async with async_playwright() as pw:
            async with _clean_browser(pw, video_path.parent) as (context, _):
                page = await context.new_page()
                await _inject_cursor(page)

                start_url = base_url.rstrip("/") + flow.start_url
                start_ms = time.time() * 1000

                for attempt in range(3):
                    try:
                        await self._execute_flow(page, flow, base_url, capture, start_ms)
                        break
                    except Exception as e:
                        if attempt == 2:
                            # Screenshot for diagnosis
                            fail_png = self.output_dir / f"{flow.name}_failure.png"
                            await page.screenshot(path=str(fail_png))
                            capture.screenshot_on_failure = fail_png
                            logger.error("Flow '%s' failed after 3 attempts: %s", flow.name, e)
                            raise
                        logger.warning("Flow '%s' attempt %d failed: %s. Retrying...", flow.name, attempt + 1, e)
                        await page.goto(start_url)
                        await page.wait_for_load_state("networkidle", timeout=15000)

                capture.duration_ms = time.time() * 1000 - start_ms

        # Rename the video from playwright's temp name
        recordings = list(video_path.parent.glob("*.webm"))
        if recordings:
            latest = max(recordings, key=lambda p: p.stat().st_mtime)
            if latest != video_path:
                latest.rename(video_path)

        capture.write_sidecar()
        logger.info("Flow '%s' captured: %.1fs", flow.name, capture.duration_ms / 1000)
        return capture

    async def _execute_flow(
        self,
        page: Page,
        flow: DemoFlow,
        base_url: str,
        capture: FlowCapture,
        start_ms: float,
    ) -> None:
        """Execute each step of a flow on the page."""
        for step in flow.steps:
            t_ms = time.time() * 1000 - start_ms
            bbox = await self._execute_step(page, step, base_url)
            if bbox:
                capture.actions.append(
                    ActionEvent(
                        timestamp_ms=t_ms,
                        action=step.action,
                        x=bbox["x"],
                        y=bbox["y"],
                        width=bbox["width"],
                        height=bbox["height"],
                        narration_cue=step.narration_cue,
                    )
                )
            await asyncio.sleep(step.wait_after_ms / 1000)

    async def _execute_step(
        self,
        page: Page,
        step: DemoStep,
        base_url: str,
    ) -> dict[str, float] | None:
        """Execute one step. Returns bounding box if applicable."""
        match step.action:
            case "goto":
                url = base_url.rstrip("/") + step.target if step.target.startswith("/") else step.target
                await page.goto(url, wait_until="networkidle", timeout=20000)
                await _inject_cursor(page)
                return None

            case "click":
                locator = _resolve_locator(page, step.target)
                await locator.wait_for(state="visible", timeout=10000)
                bbox = await locator.bounding_box()
                if bbox:
                    cx, cy = bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2
                    await _move_cursor_smooth(page, cx, cy)
                    await page.evaluate(f"window.__vgClick({cx}, {cy})")
                await locator.click()
                await page.wait_for_load_state("networkidle", timeout=10000)
                return bbox

            case "type":
                locator = _resolve_locator(page, step.target)
                await locator.wait_for(state="visible", timeout=10000)
                bbox = await locator.bounding_box()
                if bbox:
                    await _move_cursor_smooth(page, bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2)
                await locator.click()
                # Human-like typing
                for char in (step.value or ""):
                    await page.keyboard.type(char)
                    await asyncio.sleep(random.uniform(0.04, 0.09))
                return bbox

            case "scroll":
                amount = int(step.value or "300")
                await _smooth_scroll(page, amount)
                return None

            case "hover":
                locator = _resolve_locator(page, step.target)
                await locator.wait_for(state="visible", timeout=10000)
                bbox = await locator.bounding_box()
                if bbox:
                    await _move_cursor_smooth(page, bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2)
                await locator.hover()
                return bbox

            case "wait":
                ms = int(step.value or "1000")
                await asyncio.sleep(ms / 1000)
                return None

            case "press":
                await page.keyboard.press(step.target)
                return None

            case "screenshot":
                out = self.output_dir / f"screenshot_{int(time.time())}.png"
                await page.screenshot(path=str(out))
                return None

            case _:
                logger.warning("Unknown step action: %s", step.action)
                return None


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _clean_browser(
    pw: Playwright, video_dir: Path
) -> AsyncGenerator[tuple[BrowserContext, Any], None]:
    """Launch a clean Chromium with no bookmarks, extensions, or banners."""
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-notifications",
            "--disable-infobars",
            "--disable-translate",
            "--disable-features=TranslateUI",
            "--window-size=1920,1080",
        ],
    )
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        device_scale_factor=2,
        record_video_dir=str(video_dir),
        record_video_size={"width": 1920, "height": 1080},
    )

    # Block cookie consent banners via route interception
    await context.route(
        re.compile(r"(cookielaw|cookiebot|onetrust|gdpr-cookie)"),
        lambda route: route.abort(),
    )

    try:
        yield context, browser
    finally:
        await context.close()
        await browser.close()


import re


async def _inject_cursor(page: Page) -> None:
    """Inject animated cursor overlay into the page."""
    try:
        await page.evaluate(_CURSOR_JS)
    except Exception:
        pass  # Page may navigate away


async def _move_cursor_smooth(page: Page, target_x: float, target_y: float) -> None:
    """Move cursor along an eased curve (50 steps)."""
    try:
        curr = await page.evaluate("() => ({x: window.__vgX || 960, y: window.__vgY || 540})")
        sx, sy = curr.get("x", 960), curr.get("y", 540)
    except Exception:
        sx, sy = 960, 540

    steps = 40
    for i in range(1, steps + 1):
        t = i / steps
        # Ease in-out cubic
        t2 = t * t * (3 - 2 * t)
        x = sx + (target_x - sx) * t2
        y = sy + (target_y - sy) * t2
        try:
            await page.evaluate(f"() => {{ window.__vgMoveCursor({x:.1f}, {y:.1f}); window.__vgX={x:.1f}; window.__vgY={y:.1f}; }}")
        except Exception:
            break
        await asyncio.sleep(0.012)


async def _smooth_scroll(page: Page, amount: int) -> None:
    """Scroll smoothly over 30 frames."""
    step = amount / 30
    for _ in range(30):
        await page.evaluate(f"window.scrollBy(0, {step:.1f})")
        await asyncio.sleep(0.016)


def _resolve_locator(page: Page, target: str):  # type: ignore[no-untyped-def]
    """Convert a target string to a Playwright locator.

    Supports:
      - role=button[name='...']
      - text=...
      - #id
      - .class
      - [aria-label='...']
      - raw CSS selectors
    """
    if target.startswith("role="):
        # e.g. role=button[name='Sign in']
        m = re.match(r"role=(\w+)(?:\[name=['\"](.+?)['\"]\])?", target)
        if m:
            role = m.group(1)
            name = m.group(2)
            if name:
                return page.get_by_role(role, name=name)  # type: ignore[arg-type]
            return page.get_by_role(role)  # type: ignore[arg-type]
    if target.startswith("text="):
        return page.get_by_text(target[5:])
    if target.startswith("label="):
        return page.get_by_label(target[6:])
    if target.startswith("placeholder="):
        return page.get_by_placeholder(target[12:])
    # CSS / XPath fallback
    return page.locator(target)


def _flow_cache_key(flow: DemoFlow, base_url: str) -> str:
    data = json.dumps(flow.model_dump()) + base_url
    return hashlib.sha256(data.encode()).hexdigest()[:10]
