# Install

Requires **Python 3.13+**.

## From PyPI

```bash
pip install powernse
pip install 'powernse[pandas]'   # optional DataFrame helpers
powernse --help
powernse doctor
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
