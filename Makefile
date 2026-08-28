.PHONY: sync check format test build typecheck pipeline install-hooks

sync:
	uv sync

# ShipGate: install managed tools, then the full suite (full tree).
# The suite level and calibrated allowlists/thresholds now live in the versioned
# .shipgate/ policy subset (shipgate.yaml says `suite: full`), so no --suite pin
# is needed here -- a fresh clone / CI run gets the same gate.
check:
	uv run shipgate install
	uv run shipgate check --target . --full-tree

format:
	uv run shipgate install
	uv run shipgate format --target .

test:
	uv run pytest

build:
	uv build

typecheck:
	uv run shipgate install
	uv run shipgate check --check ty.check --target . --full-tree

pipeline: check test build

install-hooks:
	uv run pre-commit install
