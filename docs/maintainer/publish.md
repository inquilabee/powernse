# Publish to PyPI

Maintainer checklist for shipping `powernse`. Clients should use [Install](../user/install.md).

Do **not** push a `v*` tag until the Trusted Publisher below is registered. A premature tag burns a failed Publish run and does **not** reserve the PyPI name.

## One-time setup (first release)

`powernse` is not on PyPI yet. Use a **pending** Trusted Publisher so the first tag can create the project via OIDC.

1. GitHub repo → **Settings → Environments** → create environment named exactly **`pypi`** (optional: required reviewers).
2. On PyPI (logged in): **Publishing** → **pending trusted publisher** ([creating a project through OIDC](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)):
   - **PyPI project name:** `powernse` (pending publishers do **not** reserve the name until the first successful upload)
   - **Owner:** `inquilabee`
   - **Repository:** `powernse`
   - **Workflow filename:** `publish.yml` (the file under `.github/workflows/`, not the workflow `name:` title)
   - **Environment name:** `pypi`
3. Confirm the pending publisher shows as registered before any tag.
4. Optional later: for an **existing** PyPI project, add a trusted publisher under that project’s Publishing settings ([adding a publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)) instead of a pending one.

## Each release

1. Bump `version` in `pyproject.toml` and update `CHANGELOG.md`.
2. Commit on `main` and push.
3. Pre-flight (copy-paste):

```bash
grep '^version' pyproject.toml
# tag must match that version with a leading v, e.g. version = "0.1.0" → v0.1.0
git status -sb   # clean tree on main
```

4. Tag and push (only after step 3 of One-time setup):

```bash
git tag -a v0.1.0 -m "powernse 0.1.0"
git push origin v0.1.0
```

5. GitHub Actions [publish.yml](https://github.com/inquilabee/powernse/blob/main/.github/workflows/publish.yml) builds the sdist/wheel, asserts the tag matches the package version, smokes `import powernse`, and runs `uv publish` via OIDC.
6. Confirm https://pypi.org/project/powernse/ and `pip install -U powernse`.

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

TestPyPI needs its **own** pending/trusted publisher (or API token) and usually a separate workflow or environment. Do not assume `uv publish --publish-url https://test.pypi.org/legacy/` works with the production `pypi` publisher. Prefer the dry-run commands above unless you intentionally configure TestPyPI Trusted Publishing.
