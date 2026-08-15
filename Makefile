.PHONY: sync check test build typecheck pipeline

sync:
	uv sync

check:
	uv run ruff check src tests
	uv run ruff format --check src tests

test:
	uv run pytest

build:
	uv build

typecheck:
	test -f src/powernse/py.typed
	@echo "py.typed present; install mypy/ty in CI when you want full static checking"

pipeline: check test typecheck build
