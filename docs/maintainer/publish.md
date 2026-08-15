# Publish to PyPI

Maintainer checklist for shipping `powernse`. Clients should use [Install](../user/install.md).

## One-time setup

1. Create the project on [PyPI](https://pypi.org/) (first upload or “pending publisher”).
2. Add a **Trusted Publisher** for GitHub:
   - Owner: `inquilabee`
   - Repository: `powernse`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. In the GitHub repo, create environment **`pypi`** (Settings → Environments). Optional: require a reviewer before deploy.

## Each release

1. Bump `version` in `pyproject.toml` and update `CHANGELOG.md`.
2. Commit on `main` and push.
3. Tag and push the tag (must match the version):

```bash
git tag -a v0.1.0 -m "powernse 0.1.0"
git push origin v0.1.0
```

4. GitHub Actions [`.github/workflows/publish.yml`](../../.github/workflows/publish.yml) builds the sdist/wheel, smokes `import powernse`, and runs `uv publish` via OIDC.
5. Confirm https://pypi.org/project/powernse/ and `pip install -U powernse`.

## Local dry-run (no upload)

```bash
uv sync
make check
make test
uv build
uv run --isolated --no-project --with dist/powernse-*.whl python -c "import powernse; print(powernse.__version__)"
# optional: uv publish --publish-url https://test.pypi.org/legacy/ …
```

Do not commit `dist/`.
