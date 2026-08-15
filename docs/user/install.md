# Install

## From PyPI

```bash
pip install powernse
pip install 'powernse[pandas]'   # optional DataFrame helpers
```

Requires **Python 3.13+**.

```bash
powernse --help
powernse doctor
```

## From GitHub (before or beside PyPI)

```bash
pip install 'powernse @ git+https://github.com/inquilabee/powernse.git'
# or a tag:
pip install 'powernse @ git+https://github.com/inquilabee/powernse.git@v0.1.0'
```

## From a clone (development)

```bash
git clone https://github.com/inquilabee/powernse.git
cd powernse
uv sync
uv run powernse --help
```

## Archive root

Downloads and queries default to `./nse-data`. Override with `--root` or `POWERNSE_ROOT`.

## Next

- [Quickstart](quickstart.md)
- [Download archives](download/archives.md)
- [Fetch GitHub bundle](bundle/fetch-bundle.md)
