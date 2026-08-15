# Agents

Product contract for PowerNSE. Portable persona skills under `.cursor/skills/` still apply; this file is what is true **here**.

## Purpose

Ship a publishable Python package that downloads official NSE equity archives and lets users load them via CLI and a small public API. Vision: [docs/product/vision.md](docs/product/vision.md).

## Layout

```text
src/powernse/          # package (http, archive, downloaders, cli, loaders)
tests/                 # pytest
docs/product/vision.md
docs/user/quickstart.md
```

Public surface: `powernse` package front (`NSEData`, downloaders) + one console script `powernse`.

## Commands

| Task | Command |
| --- | --- |
| Sync | `uv sync` |
| Quality | `make check` (ShipGate `install` + `check --full-tree`) |
| Format | `make format` |
| Test | `make test` / `uv run pytest` |
| Build | `make build` / `uv build` |
| Hooks | `make install-hooks` |

Policy: [`.shipgate/shipgate.yaml`](.shipgate/shipgate.yaml) (`suite: standard`). Docs: https://inquilabee.github.io/shipgate/

`make check` / pre-commit / CI always use `--full-tree`. Bare `shipgate check` honors `changed-only: true` in policy and may scan fewer files. Do not call `uv run ruff` for gates — Ruff runs via ShipGate managed tools; lint settings stay in `[tool.ruff]`.

## Rules of thumb

- Prefer official `nsearchives.nseindia.com` and documented NSE JSON APIs.
- Do not add a Kaggle (or other third-party dump) download path.
- Keep the public API small: `NSEData` + downloaders + settings/errors (`ArchiveReader` is a compatibility alias).
- Never bypass quality hooks when they are installed (`make check` / pre-commit ShipGate gates).
