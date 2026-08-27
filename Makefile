.PHONY: sync check format test build typecheck pipeline install-hooks

sync:
	uv sync

# ShipGate: install managed tools, then report-only standard suite (full tree).
# --suite is pinned explicitly: .shipgate/shipgate.yaml is gitignored (local-only),
# so nothing in version control fixes the suite level otherwise -- a fresh clone or
# CI run would fall back to whatever shipgate's own default is, silently diverging
# from this repo's calibrated "standard" allowlists/thresholds.
check:
	uv run shipgate install
	uv run shipgate check --target . --full-tree --suite standard

format:
	uv run shipgate install
	uv run shipgate format --target .

test:
	uv run pytest

build:
	uv build

typecheck:
	uv run shipgate install
	uv run shipgate check --check ty.check --target . --full-tree --suite standard

pipeline: check test build

install-hooks:
	uv run pre-commit install
