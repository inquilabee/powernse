# Install

Requires **Python 3.13+**.

## From GitHub (works today)

Until the first PyPI release (`v0.1.0`) is published, install from GitHub:

```bash
pip install 'powernse @ git+https://github.com/inquilabee/powernse.git'
pip install 'powernse[pandas] @ git+https://github.com/inquilabee/powernse.git'  # optional
powernse --help
powernse doctor
```

## From PyPI (after first release)

```bash
pip install powernse
pip install 'powernse[pandas]'   # optional DataFrame helpers
powernse --help
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
