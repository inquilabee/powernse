.PHONY: sync check test build

sync:
	uv sync

check:
	uv run ruff check src tests
	uv run ruff format --check src tests

test:
	uv run pytest

build:
	uv build

pipeline: check test build
