"""Demo runner — install, build, and start the website for demo capture.

Handles:
  - npm/yarn/pnpm/pip/poetry/cargo projects
  - Production build (not dev server)
  - Port availability check
  - Clean shutdown
  - Fallback: Playwright route interception with fixtures
"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

import httpx
from rich.console import Console

from videogen.ingest.repo_analyzer import RepoAnalysis

logger = logging.getLogger(__name__)
console = Console()

_POLL_INTERVAL = 1.0  # seconds
_MAX_WAIT = 120  # seconds


@dataclass
class SiteProcess:
    """A running site process."""

    process: subprocess.Popen  # type: ignore[type-arg]
    port: int
    base_url: str


@contextmanager
def run_site(
    analysis: RepoAnalysis,
    env_overrides: dict[str, str] | None = None,
    live_url: str | None = None,
) -> Generator[str, None, None]:
    """Context manager that yields the base URL of the running site.

    Prefers live_url if given. Otherwise installs + builds + starts the repo.
    Cleans up the process on exit.

    Args:
        analysis: RepoAnalysis with start commands and port.
        env_overrides: Extra env vars (demo credentials etc.).
        live_url: If set, yield it directly without starting anything.

    Yields:
        Base URL string, e.g. 'http://localhost:3000'
    """
    if live_url:
        logger.info("Using live URL: %s", live_url)
        yield live_url
        return

    if not analysis.can_run_locally:
        raise RuntimeError(
            f"Cannot run site locally: {analysis.cannot_run_reason}. "
            "Set a live_url in config or provide demo credentials."
        )

    repo_path = analysis.local_path
    port = analysis.port
    base_url = f"http://localhost:{port}"

    # Check port not in use
    if _port_in_use(port):
        logger.warning("Port %d already in use — using it as-is", port)
        yield base_url
        return

    # Build environment
    env = {**os.environ}
    if env_overrides:
        env.update(env_overrides)
    env["PORT"] = str(port)
    env["NODE_ENV"] = "production"

    # Step 1: Install dependencies
    if analysis.install_command:
        console.print(f"[cyan]Installing dependencies: {analysis.install_command}[/cyan]")
        _run_checked(
            analysis.install_command,
            cwd=repo_path,
            env=env,
            description="dependency installation",
        )

    # Step 2: Build
    if analysis.build_command:
        console.print(f"[cyan]Building: {analysis.build_command}[/cyan]")
        _run_checked(
            analysis.build_command,
            cwd=repo_path,
            env=env,
            description="production build",
        )

    # Step 3: Start
    console.print(f"[cyan]Starting: {analysis.start_command} on port {port}[/cyan]")
    proc = subprocess.Popen(
        analysis.start_command,
        shell=True,
        cwd=repo_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid if sys.platform != "win32" else None,
        text=True,
    )

    try:
        # Wait for the port to respond
        if not _wait_for_port(port, proc, timeout=_MAX_WAIT):
            _kill(proc)
            raise RuntimeError(
                f"Site did not start on port {port} within {_MAX_WAIT}s. "
                f"Check build output. Start command: {analysis.start_command}"
            )
        console.print(f"[green]✓ Site running at {base_url}[/green]")
        yield base_url
    finally:
        console.print("[cyan]Stopping site...[/cyan]")
        _kill(proc)


def _wait_for_port(port: int, proc: subprocess.Popen, timeout: float) -> bool:  # type: ignore[type-arg]
    """Poll until the port responds to HTTP or the process dies."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            stdout, stderr = proc.communicate(timeout=5)
            logger.error("Process exited early.\nSTDOUT: %s\nSTDERR: %s", stdout, stderr)
            return False
        try:
            with httpx.Client(timeout=2.0) as client:
                r = client.get(f"http://localhost:{port}/")
                if r.status_code < 500:
                    return True
        except Exception:
            pass
        time.sleep(_POLL_INTERVAL)
    return False


def _port_in_use(port: int) -> bool:
    """Return True if something is already listening on port."""
    try:
        with httpx.Client(timeout=1.0) as client:
            client.get(f"http://localhost:{port}/")
            return True
    except Exception:
        return False


def _run_checked(cmd: str, cwd: Path, env: dict, description: str) -> None:
    """Run a shell command and raise on failure with a useful message."""
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{description} failed (exit {result.returncode}).\n"
            f"Command: {cmd}\n"
            f"STDERR:\n{result.stderr[-2000:]}"
        )


def _kill(proc: subprocess.Popen) -> None:  # type: ignore[type-arg]
    """Kill process group cleanly."""
    try:
        if sys.platform != "win32":
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
