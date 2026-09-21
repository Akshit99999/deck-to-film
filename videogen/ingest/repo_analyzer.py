"""Repo analyzer — clone + analyze a website repository.

Determines:
  - Purpose / product description
  - Tech stack (framework, package manager, language)
  - Routes / pages
  - Main user flows
  - Auth requirements
  - Required env vars (names only, never values)
  - How to install, build, and start the app
  - Whether a production build is feasible
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# File patterns that should never be read (secrets, lock files, large binary)
_SKIP_PATTERNS = re.compile(
    r"(node_modules|\.git|dist|build|\.next|__pycache__|\.pnp|"
    r"package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|"
    r"Cargo\.lock|\.env|\.env\.\w+|\.pem|\.key|id_rsa|id_ed25519|"
    r"\.(png|jpg|jpeg|gif|webp|ico|svg|woff|woff2|ttf|otf|eot|mp4|mp3|"
    r"pdf|zip|tar|gz|bin|exe|dll|so|dylib)$)",
    re.IGNORECASE,
)
_MAX_FILE_SIZE = 64 * 1024  # 64 KB per file
_MAX_FILES_TOTAL = 80  # files sent to LLM context


@dataclass
class RepoAnalysis:
    """Results of analyzing a website repository."""

    repo_url: str
    local_path: Path
    framework: str
    package_manager: str  # npm | yarn | pnpm | pip | poetry | cargo | ...
    language: str  # TypeScript | JavaScript | Python | ...
    build_command: str
    start_command: str
    port: int
    install_command: str
    routes: list[str] = field(default_factory=list)
    main_flows: list[str] = field(default_factory=list)
    auth_required: bool = False
    env_vars_needed: list[str] = field(default_factory=list)  # names only, no values
    description: str = ""
    can_run_locally: bool = True
    cannot_run_reason: str = ""

    def to_dict(self) -> dict:  # type: ignore[return]
        return {
            "repo_url": self.repo_url,
            "framework": self.framework,
            "package_manager": self.package_manager,
            "language": self.language,
            "build_command": self.build_command,
            "start_command": self.start_command,
            "port": self.port,
            "install_command": self.install_command,
            "routes": self.routes,
            "main_flows": self.main_flows,
            "auth_required": self.auth_required,
            "env_vars_needed": self.env_vars_needed,
            "description": self.description,
            "can_run_locally": self.can_run_locally,
            "cannot_run_reason": self.cannot_run_reason,
        }


def clone_repo(repo_url: str, target_dir: Path) -> Path:
    """Shallow-clone a git repo into target_dir.

    Args:
        repo_url: HTTPS/SSH URL or local path.
        target_dir: Parent directory to clone into.

    Returns:
        Path to the cloned repo root.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    # If local path, just return it
    repo_path = Path(repo_url)
    if repo_path.exists() and repo_path.is_dir():
        logger.info("Using local repo: %s", repo_url)
        return repo_path

    # Clone
    dest = target_dir / _repo_name(repo_url)
    if dest.exists():
        logger.info("Repo already cloned at %s, skipping clone", dest)
        return dest

    logger.info("Cloning %s → %s", repo_url, dest)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", repo_url, str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    return dest


def analyze_repo(repo_path: Path, repo_url: str) -> RepoAnalysis:
    """Analyze a local repo to determine tech stack and how to run it.

    This is a static analysis pass — no code is executed here.
    """
    logger.info("Analyzing repo at %s", repo_path)

    analysis = RepoAnalysis(
        repo_url=repo_url,
        local_path=repo_path,
        framework="unknown",
        package_manager="npm",
        language="JavaScript",
        build_command="",
        start_command="",
        port=3000,
        install_command="npm install",
    )

    # Detect package manager
    if (repo_path / "pnpm-lock.yaml").exists():
        analysis.package_manager = "pnpm"
    elif (repo_path / "yarn.lock").exists():
        analysis.package_manager = "yarn"
    elif (repo_path / "pyproject.toml").exists():
        analysis.package_manager = "poetry" if (repo_path / "poetry.lock").exists() else "pip"
        analysis.language = "Python"
    elif (repo_path / "requirements.txt").exists():
        analysis.package_manager = "pip"
        analysis.language = "Python"
    elif (repo_path / "Cargo.toml").exists():
        analysis.package_manager = "cargo"
        analysis.language = "Rust"

    # Detect JS framework via package.json
    pkg_json = repo_path / "package.json"
    if pkg_json.exists():
        _detect_js_framework(pkg_json, analysis)

    # Detect Python framework
    if analysis.language == "Python":
        _detect_python_framework(repo_path, analysis)

    # Detect env vars needed
    analysis.env_vars_needed = _find_env_var_names(repo_path)

    # Detect routes
    analysis.routes = _find_routes(repo_path, analysis.framework)

    # Infer auth
    analysis.auth_required = _has_auth(repo_path)

    # Set install command
    analysis.install_command = {
        "npm": "npm install",
        "yarn": "yarn install",
        "pnpm": "pnpm install",
        "pip": "pip install -r requirements.txt",
        "poetry": "poetry install",
        "cargo": "cargo build --release",
    }.get(analysis.package_manager, "npm install")

    logger.info(
        "Detected: framework=%s pm=%s lang=%s port=%d",
        analysis.framework,
        analysis.package_manager,
        analysis.language,
        analysis.port,
    )
    return analysis


def _detect_js_framework(pkg_json: Path, analysis: RepoAnalysis) -> None:
    """Read package.json to detect framework, build/start commands, and port."""
    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
    except Exception:
        return

    deps = {
        **data.get("dependencies", {}),
        **data.get("devDependencies", {}),
    }

    scripts: dict[str, str] = data.get("scripts", {})

    # TypeScript?
    if "typescript" in deps or any(k.endswith(".ts") for k in list(deps.keys())[:5]):
        analysis.language = "TypeScript"

    # Framework detection (order matters — check more specific first)
    if "next" in deps:
        analysis.framework = "next.js"
        analysis.port = 3000
        analysis.build_command = f"{analysis.package_manager} run build" if analysis.package_manager != "npm" else "npm run build"
        analysis.start_command = f"{analysis.package_manager} run start" if analysis.package_manager != "npm" else "npm run start"
    elif "nuxt" in deps or "nuxt3" in deps:
        analysis.framework = "nuxt"
        analysis.port = 3000
        analysis.build_command = "nuxt build"
        analysis.start_command = "node .output/server/index.mjs"
    elif "vite" in deps:
        analysis.framework = "vite"
        analysis.port = 4173
        analysis.build_command = "vite build"
        analysis.start_command = "vite preview --port 4173"
    elif "@angular/core" in deps:
        analysis.framework = "angular"
        analysis.port = 4200
        analysis.build_command = "ng build --configuration production"
        analysis.start_command = "npx serve dist/app -l 4200"
    elif "react" in deps and "react-scripts" in deps:
        analysis.framework = "create-react-app"
        analysis.port = 3000
        analysis.build_command = "react-scripts build"
        analysis.start_command = "npx serve -s build -l 3000"
    elif "svelte" in deps:
        analysis.framework = "svelte/sveltekit"
        analysis.port = 4173
        analysis.build_command = "vite build"
        analysis.start_command = "vite preview --port 4173"
    elif "gatsby" in deps:
        analysis.framework = "gatsby"
        analysis.port = 9000
        analysis.build_command = "gatsby build"
        analysis.start_command = "gatsby serve --port 9000"
    elif "astro" in deps:
        analysis.framework = "astro"
        analysis.port = 4321
        analysis.build_command = "astro build"
        analysis.start_command = "astro preview --port 4321"
    elif "remix" in deps or "@remix-run/react" in deps:
        analysis.framework = "remix"
        analysis.port = 3000
        analysis.build_command = "remix build"
        analysis.start_command = "remix-serve build"
    elif "express" in deps or "fastify" in deps or "koa" in deps:
        analysis.framework = "node-api"
        analysis.port = int(_extract_port_from_scripts(scripts) or 3000)
        analysis.build_command = scripts.get("build", "")
        analysis.start_command = scripts.get("start", "node index.js")
    else:
        # Fallback: use scripts
        analysis.build_command = scripts.get("build", "")
        analysis.start_command = scripts.get("start", "")
        analysis.port = 3000

    # Override with explicit port in scripts if detectable
    detected_port = _extract_port_from_scripts(scripts)
    if detected_port:
        analysis.port = detected_port

    # Override build/start from scripts if we found them
    if not analysis.build_command and "build" in scripts:
        pm = analysis.package_manager
        analysis.build_command = f"{pm} run build"
    if not analysis.start_command and "start" in scripts:
        pm = analysis.package_manager
        analysis.start_command = f"{pm} run start"


def _detect_python_framework(repo_path: Path, analysis: RepoAnalysis) -> None:
    """Detect Python web framework (Django, Flask, FastAPI)."""
    # Check imports across Python files
    py_files = list(repo_path.rglob("*.py"))[:30]
    content = ""
    for f in py_files:
        try:
            content += f.read_text(encoding="utf-8", errors="ignore")[:2000]
        except Exception:
            pass

    if "django" in content.lower():
        analysis.framework = "django"
        analysis.port = 8000
        analysis.build_command = "python manage.py collectstatic --noinput"
        analysis.start_command = "gunicorn wsgi:application --bind 0.0.0.0:8000"
    elif "fastapi" in content.lower() or "uvicorn" in content.lower():
        analysis.framework = "fastapi"
        analysis.port = 8000
        analysis.build_command = ""
        analysis.start_command = "uvicorn main:app --host 0.0.0.0 --port 8000"
    elif "flask" in content.lower():
        analysis.framework = "flask"
        analysis.port = 5000
        analysis.build_command = ""
        analysis.start_command = "flask run --host 0.0.0.0 --port 5000"
    else:
        analysis.framework = "python-web"
        analysis.port = 8000


def _extract_port_from_scripts(scripts: dict[str, str]) -> int | None:
    """Try to find a port number in npm scripts."""
    for v in scripts.values():
        m = re.search(r"(?:--port|-p)\s+(\d{4,5})", v)
        if m:
            return int(m.group(1))
    return None


def _find_env_var_names(repo_path: Path) -> list[str]:
    """Find env var names used in the codebase (no values)."""
    env_names: set[str] = set()

    # Read .env.example or .env.sample
    for fname in (".env.example", ".env.sample", ".env.template"):
        f = repo_path / fname
        if f.exists():
            for line in f.read_text(errors="ignore").splitlines():
                m = re.match(r"^([A-Z_][A-Z0-9_]+)\s*=", line.strip())
                if m:
                    env_names.add(m.group(1))

    # Scan source files for process.env.X or os.environ.get('X')
    patterns = [
        re.compile(r"process\.env\.([A-Z_][A-Z0-9_]+)"),
        re.compile(r"os\.environ\.get\(['\"]([A-Z_][A-Z0-9_]+)"),
        re.compile(r"os\.getenv\(['\"]([A-Z_][A-Z0-9_]+)"),
        re.compile(r"import\.meta\.env\.([A-Z_][A-Z0-9_]+)"),
    ]

    for src in _walk_source_files(repo_path, limit=40):
        try:
            text = src.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in patterns:
            for m in pat.finditer(text):
                name = m.group(1)
                if name not in ("NODE_ENV", "PATH", "HOME", "USER"):
                    env_names.add(name)

    return sorted(env_names)


def _find_routes(repo_path: Path, framework: str) -> list[str]:
    """Detect URL routes/pages from file structure."""
    routes: list[str] = []

    # Next.js / Nuxt: pages directory
    for pages_dir in (
        repo_path / "pages",
        repo_path / "app",  # Next.js 13 app router
        repo_path / "src" / "pages",
        repo_path / "src" / "app",
    ):
        if pages_dir.exists():
            for f in pages_dir.rglob("*.{tsx,jsx,ts,js,vue,svelte}"):
                rel = f.relative_to(pages_dir)
                route = "/" + str(rel).replace("\\", "/")
                # Clean up
                route = re.sub(r"\.(tsx|jsx|ts|js|vue|svelte)$", "", route)
                route = re.sub(r"/index$", "", route)
                route = re.sub(r"\[(.+?)\]", r":\1", route)  # [slug] → :slug
                if route and route not in routes:
                    routes.append(route)

    # Django: look at urls.py
    if framework == "django":
        for urls_file in repo_path.rglob("urls.py"):
            try:
                content = urls_file.read_text()
                for m in re.finditer(r"path\(['\"]([^'\"]+)['\"]", content):
                    routes.append("/" + m.group(1))
            except Exception:
                pass

    return sorted(set(routes))[:30]  # cap for LLM


def _has_auth(repo_path: Path) -> bool:
    """Heuristically detect if the app has authentication."""
    auth_indicators = ["login", "logout", "signin", "signup", "auth", "jwt", "passport", "session"]
    for src in _walk_source_files(repo_path, limit=20):
        try:
            text = src.read_text(encoding="utf-8", errors="ignore").lower()
            if any(ind in text for ind in auth_indicators):
                return True
        except Exception:
            pass
    return False


def _walk_source_files(repo_path: Path, limit: int = 80) -> list[Path]:
    """Walk source files, skipping heavy/secret files."""
    result: list[Path] = []
    for f in repo_path.rglob("*"):
        if len(result) >= limit:
            break
        if not f.is_file():
            continue
        if _SKIP_PATTERNS.search(str(f)):
            continue
        if f.stat().st_size > _MAX_FILE_SIZE:
            continue
        result.append(f)
    return result


def collect_source_for_llm(repo_path: Path) -> str:
    """Collect source file contents for LLM analysis.

    Returns a text dump of the most important source files,
    never including .env contents, secrets, lockfiles, or node_modules.
    """
    files = _walk_source_files(repo_path, limit=_MAX_FILES_TOTAL)
    parts: list[str] = [f"# Repository: {repo_path.name}\n"]

    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Extra guard: skip if content looks like a .env file (key=value pairs with secrets)
        if re.search(r"(?:SECRET|PASSWORD|TOKEN|KEY)\s*=\s*[^\s$]", content, re.IGNORECASE):
            parts.append(f"\n## {f.relative_to(repo_path)} [REDACTED - contains secrets]\n")
            continue

        rel = f.relative_to(repo_path)
        parts.append(f"\n## {rel}\n```\n{content[:8000]}\n```")

    return "\n".join(parts)


def _repo_name(url: str) -> str:
    """Extract repo name from URL."""
    name = url.rstrip("/").split("/")[-1]
    return re.sub(r"\.git$", "", name)
