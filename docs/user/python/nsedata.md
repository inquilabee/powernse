# Use NSEData in Python

OHLC helpers scan each day's full CSV — use modest date windows unless you add your own index.

## Try this

```python
from datetime import date
from powernse import NSEData

data = NSEData("./nse-data")

bars = data.ohlc("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
latest = data.latest("RELIANCE")
gaps = data.coverage_gaps(from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))

# Opt-in bonus/split adjustment from staged corporate-actions JSON
adjusted = data.ohlc_adjusted("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))

fo = data.fo_bars("RELIANCE", instrument_type="FUTSTK")
indexes = data.index_ohlc("Nifty 50", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
full_rows = data.full_bhavcopy_rows(date(2024, 8, 9))
bulk = data.bulk_deals(date(2024, 8, 9))

print(data.inventory())
```

With pandas:

```bash
pip install 'powernse[pandas]'
```

```python
frame = data.ohlc_frame("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
```

## What you should see

- `ohlc` / `ohlc_adjusted` return lists of bars (empty list if no matches; CLI `ohlc` exits `1` when empty)
- `inventory()` counts files per archive prefix
- Missing required files raise `ArchiveError`

`ohlc_adjusted` only applies ratios it can parse from corporate-action subjects (bonus `A:B`, common face-value splits). Unrecognized subjects are skipped.

## Next

- [Download archives](../download/archives.md)
- [Fetch bundle](../bundle/fetch-bundle.md)
