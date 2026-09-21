.PHONY: install dev-install test typecheck lint clean docker-build \
        plan demo voice captions render preview

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"
	playwright install chromium --with-deps
	cd remotion && npm install

# ── Quality ───────────────────────────────────────────────────────────────────

test:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v --tb=short

test-e2e:
	pytest tests/e2e/ -v --tb=short

typecheck:
	mypy videogen/

lint:
	ruff check videogen/ tests/

lint-fix:
	ruff check --fix videogen/ tests/

# ── Pipeline stages ───────────────────────────────────────────────────────────

plan:
	videogen plan --config videogen.yaml

demo:
	videogen demo --config videogen.yaml

voice:
	videogen voice --config videogen.yaml

captions:
	videogen captions --config videogen.yaml

render:
	videogen render --config videogen.yaml

preview:
	videogen preview --config videogen.yaml

build:
	videogen build --config videogen.yaml

dry-run:
	videogen build --config videogen.yaml --dry-run

# ── Docker ────────────────────────────────────────────────────────────────────

docker-build:
	docker build -t videogen:latest .

docker-run:
	docker compose run --rm videogen build --config /workspace/videogen.yaml

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	rm -rf build/ out/ .mypy_cache/ .ruff_cache/ __pycache__ \
	       dist/ *.egg-info .pytest_cache
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
