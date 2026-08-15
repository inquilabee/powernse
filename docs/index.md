# PowerNSE

Download and use **official NSE India** equity archives from the CLI or a small Python API.

- CM / F&O / full bhavcopy, index closes, deals, corporate actions, index constituents
- Local `nse-data/` archive + download manifest
- `fetch-bundle` — pull the tracked archive tree from GitHub
- Optional `powernse[pandas]` DataFrame helpers

**Requires Python 3.13+.**

```bash
pip install 'powernse @ git+https://github.com/inquilabee/powernse.git'
# after PyPI: pip install powernse
powernse bhavcopy --resume
powernse fetch-bundle --force
powernse ohlc RELIANCE --from 2024-08-01 --to 2024-08-05
```

```python
from datetime import date
from powernse import NSEData

data = NSEData("./nse-data")
bars = data.ohlc("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
```

## Next

- [Install](user/install.md)
- [Quickstart](user/quickstart.md)
- [Download archives](user/download/archives.md)
- [GitHub](https://github.com/inquilabee/powernse) · [Changelog](https://github.com/inquilabee/powernse/blob/main/CHANGELOG.md)
