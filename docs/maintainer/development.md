# Development

Maintainer workflow for hacking on `powernse`. Clients should use
[Install](../user/install.md) — this page is for contributors.

```bash
uv sync
make check    # ShipGate
make format
make test
make build
```

Local docs site: `uv run --with mkdocs-material mkdocs serve`.

Quality gates: [ShipGate](https://inquilabee.github.io/shipgate/) (`suite: standard`).
Release steps: [Publish](publish.md).
