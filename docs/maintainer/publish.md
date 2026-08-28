# Publish to PyPI

Maintainer checklist for shipping `powernse`. Clients install from
[PyPI](https://pypi.org/project/powernse/) — see [Install](../user/install.md).

Live project: <https://pypi.org/project/powernse/> (first release: **0.1.0**).

Do **not** push a `v*` tag until the Trusted Publisher below is registered for
this repo. A mismatched publisher fails the Publish job.

## Trusted Publisher (already set for this repo)

GitHub environment **`pypi`** + a Trusted Publisher on the PyPI project
`powernse` pointing at:

| Field | Value |
| --- | --- |
| Owner | `inquilabee` |
| Repository | `powernse` |
| Workflow filename | `publish.yml` |
| Environment name | `pypi` |

Manage publishers under the project’s **Publishing** settings
([adding a publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)).
For a **new** empty name on PyPI you would use a
[pending trusted publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
instead — that path was used for the first upload and is no longer needed here.

If the GitHub `pypi` environment is missing: **Settings → Environments →**
create it named exactly `pypi`.

## Each release

1. Bump `version` in `pyproject.toml` and update `CHANGELOG.md`.
2. Commit on `main` and push.
3. Pre-flight (copy-paste):

   ```bash
   grep '^version' pyproject.toml
   # tag must match that version with a leading v, e.g. version = "0.2.0" → v0.2.0
   git status -sb   # clean tree on main
   ```

4. Tag and push:

   ```bash
   git tag -a v0.2.0 -m "powernse 0.2.0"
   git push origin v0.2.0
   ```

5. GitHub Actions [publish.yml](https://github.com/inquilabee/powernse/blob/main/.github/workflows/publish.yml)
   builds the sdist/wheel, asserts the tag matches the package version, smokes
   `import powernse`, and runs `uv publish` via OIDC.
6. Confirm <https://pypi.org/project/powernse/> and `pip install -U powernse`.

## Local dry-run (no upload)

```bash
uv sync
make check
make test
uv build
uv run --isolated --no-project --with dist/powernse-*.whl python -c "import powernse; print(powernse.__version__)"
```

Do not commit `dist/`.

### TestPyPI (optional)

TestPyPI needs its **own** pending/trusted publisher (or API token) and usually a
separate workflow or environment. Do not assume
`uv publish --publish-url https://test.pypi.org/legacy/` works with the
production `pypi` publisher. Prefer the dry-run commands above unless you
intentionally configure TestPyPI Trusted Publishing.
