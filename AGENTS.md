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

Public surface: `powernse` package front + one console script `powernse`.

## Commands

| Task | Command |
| --- | --- |
| Sync | `uv sync` |
| Lint | `make check` |
| Test | `make test` / `uv run pytest` |
| Build | `make build` / `uv build` |

## Rules of thumb

- Prefer official `nsearchives.nseindia.com` and documented NSE JSON APIs.
- Do not add a Kaggle (or other third-party dump) download path.
- Keep the public API small: downloaders + `ArchiveReader` + settings/errors.
- Never bypass quality hooks when they are installed.
