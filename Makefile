.PHONY: install lint format test render-dev run-now run-morning run-afternoon run-evening logs

# ── Dependencies ──────────────────────────────────────────────────────────────

install:
	pip install -e ".[dev]"
	cd remotion && npm ci

# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	ruff check .
	ruff format --check .
	cd remotion && npx tsc --noEmit

format:
	ruff format .

# ── Tests ─────────────────────────────────────────────────────────────────────

test:
	pytest tests/ -v

# ── Remotion development ──────────────────────────────────────────────────────

render-dev:
	cd remotion && npx remotion studio

# ── Pipeline execution ────────────────────────────────────────────────────────

run-now:
	python -m agents.scheduler --run-now

run-morning:
	python -m agents.scheduler --run-now --slot morning

run-afternoon:
	python -m agents.scheduler --run-now --slot afternoon

run-evening:
	python -m agents.scheduler --run-now --slot evening

# ── Observability ─────────────────────────────────────────────────────────────

logs:
	tail -f logs/pipeline.log
