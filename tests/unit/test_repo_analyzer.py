"""Unit tests for repo_analyzer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from videogen.ingest.repo_analyzer import (
    RepoAnalysis,
    _detect_js_framework,
    _find_env_var_names,
    _find_routes,
    _has_auth,
)


def _write_pkg_json(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "package.json"
    p.write_text(json.dumps(data))
    return p


class TestFrameworkDetection:
    def test_next_js(self, tmp_path: Path) -> None:
        _write_pkg_json(
            tmp_path,
            {
                "dependencies": {"next": "14.0.0", "react": "18.0.0"},
                "scripts": {"build": "next build", "start": "next start"},
            },
        )
        analysis = RepoAnalysis(
            repo_url="", local_path=tmp_path, framework="",
            package_manager="npm", language="JavaScript",
            build_command="", start_command="", port=3000,
            install_command="npm install",
        )
        _detect_js_framework(tmp_path / "package.json", analysis)
        assert analysis.framework == "next.js"
        assert analysis.port == 3000

    def test_vite(self, tmp_path: Path) -> None:
        _write_pkg_json(tmp_path, {"dependencies": {"vite": "5.0.0"}})
        analysis = RepoAnalysis(
            repo_url="", local_path=tmp_path, framework="",
            package_manager="npm", language="JavaScript",
            build_command="", start_command="", port=3000,
            install_command="npm install",
        )
        _detect_js_framework(tmp_path / "package.json", analysis)
        assert analysis.framework == "vite"
        assert analysis.port == 4173

    def test_typescript_detected(self, tmp_path: Path) -> None:
        _write_pkg_json(
            tmp_path,
            {"dependencies": {"next": "14.0.0"}, "devDependencies": {"typescript": "5.0.0"}},
        )
        analysis = RepoAnalysis(
            repo_url="", local_path=tmp_path, framework="",
            package_manager="npm", language="JavaScript",
            build_command="", start_command="", port=3000,
            install_command="npm install",
        )
        _detect_js_framework(tmp_path / "package.json", analysis)
        assert analysis.language == "TypeScript"


class TestEnvVarDetection:
    def test_env_example(self, tmp_path: Path) -> None:
        (tmp_path / ".env.example").write_text(
            "DATABASE_URL=postgres://...\nNEXT_PUBLIC_API_URL=https://...\nSECRET_KEY=\n"
        )
        names = _find_env_var_names(tmp_path)
        assert "DATABASE_URL" in names
        assert "NEXT_PUBLIC_API_URL" in names

    def test_process_env_in_source(self, tmp_path: Path) -> None:
        src = tmp_path / "app.ts"
        src.write_text("const key = process.env.STRIPE_SECRET_KEY;")
        names = _find_env_var_names(tmp_path)
        assert "STRIPE_SECRET_KEY" in names

    def test_no_values_in_output(self, tmp_path: Path) -> None:
        (tmp_path / ".env.example").write_text("API_KEY=my-secret-value\n")
        names = _find_env_var_names(tmp_path)
        assert "API_KEY" in names
        assert "my-secret-value" not in names


class TestAuthDetection:
    def test_auth_detected(self, tmp_path: Path) -> None:
        (tmp_path / "auth.ts").write_text(
            "import passport from 'passport';\nif (req.session.user) {}"
        )
        assert _has_auth(tmp_path) is True

    def test_no_auth(self, tmp_path: Path) -> None:
        (tmp_path / "index.ts").write_text("console.log('hello world');")
        assert _has_auth(tmp_path) is False


class TestRouteDetection:
    def test_nextjs_pages(self, tmp_path: Path) -> None:
        pages = tmp_path / "pages"
        pages.mkdir()
        (pages / "index.tsx").write_text("")
        (pages / "about.tsx").write_text("")

        routes = _find_routes(tmp_path, "next.js")
        assert any("about" in r for r in routes)
