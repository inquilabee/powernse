# Use NSEData in Python

OHLC helpers scan each day's full CSV — use modest date windows unless you add your
own index. Long symbol queries are O(trading days × rows per day). Every bulk query
returns a `pandas.DataFrame`; a single-record lookup like `latest()` returns a
`pandas.Series` (or `None`).

## Try this

```python
from datetime import date
from powernse import NSEData

data = NSEData("./nse-data")

frame = data.ohlc("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
latest = data.latest("RELIANCE")  # pandas.Series | None, one OHLC row
gaps = data.coverage_gaps(from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))

# Opt-in bonus/split/dividend adjustment from staged corporate-actions JSON
# (loads CA files from a bounded lookback window before from_date so ex-dates in-window are found)
adjusted = data.ohlc_adjusted("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))

fo = data.fo_bars("RELIANCE", instrument_type="FUTSTK")
indexes = data.index_ohlc("Nifty 50", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
full_rows = data.full_bhavcopy_rows(date(2024, 8, 9))
bulk = data.bulk_deals(date(2024, 8, 9))

print(data.inventory())
```

Other DataFrame helpers (pandas is a core dependency):

```python
day = data.bhavcopy_frame(date(2024, 8, 5))  # full raw CSV columns, unnormalized

# Date x Symbol matrix for one OHLCV column, read across staged days in a single pass
close = data.wide_frame(column="close", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
```

Corporate actions (see `powernse.CorporateActions` for the classifier and per-record frame):

```python
from powernse import CorporateActions

actions = CorporateActions(data).frame("RELIANCE", from_date=date(2024, 1, 1), to_date=date(2024, 8, 5))
```

## What you should see

- `ohlc`, `ohlc_adjusted`, `fo_bars`, `index_ohlc`, `on` return `pandas.DataFrame` (empty
  DataFrame — same columns, zero rows — if no matches; CLI `ohlc` exits `1` when empty)
- `latest()` returns a one-row `pandas.Series`, or `None` if nothing is staged yet
- `inventory()` counts files per archive prefix
- Missing required files raise `ArchiveError`

`ohlc_adjusted` applies bonus (`A:B`), face-value split, and dividend adjustments parsed
from corporate-action subjects; unrecognized subjects are skipped. Dividend adjustment
uses the close on the prior trading day, so it needs OHLC bars loaded before the CA
records.

Each DataFrame-returning method validates its result against a `powernse.schemas` schema
(`OhlcSchema`, `AdjustedOhlcSchema`, `FoSchema`, `IndexSchema`) before returning it — the
same column/type/nullability contract the old `OhlcBar`/`AdjustedOhlcBar`/`FoBar`/
`IndexBar` dataclasses used to enforce. Validate your own frames the same way if you build
one by hand:

```python
from powernse import OhlcSchema

OhlcSchema().validate(frame)  # raises pdschema.SchemaValidationError on mismatch
```

## Next

- [Install](../install.md)
- [Download archives](../download/archives.md)
- [Fetch bundle](../bundle/fetch-bundle.md)
