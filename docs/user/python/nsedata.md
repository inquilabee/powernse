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

# Corporate-action adjustment from staged CA JSON (loads a bounded lookback window
# before from_date so in-window ex-dates are found). Default: bonus/split/
# consolidation/dividend; pass include=(...,"rights") to also apply rights issues.
adjusted = data.ohlc_adjusted("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
with_rights = data.ohlc_adjusted(
    "RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5),
    include=("bonus", "split", "consolidation", "dividend", "rights"),
)

fo = data.fo_bars("RELIANCE", instrument_type="FUTSTK")
indexes = data.index("Nifty 50").ohlc(from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
full_rows = data.full_bhavcopy_rows(date(2024, 8, 9))

print(data.inventory())
```

```python
# Bulk / block deals across the staged window (DealSchema-shaped); filter by symbol / side
bulk = data.bulk_deals(from_date=date(2024, 8, 1), to_date=date(2024, 8, 9), symbol="RELIANCE")
block = data.block_deals(side="BUY")

# F&O trade ban, keyed by the effective trade date parsed from each file's header
banned = data.secban()                       # set[str] for the latest staged ban date
data.is_banned("SAIL", date(2024, 8, 9))     # bool
```

```python
# Date x Symbol matrix for one OHLCV column, read across staged days in a single pass
close = data.wide_frame(column="close", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
adj_close = data.wide_frame(from_date=date(2024, 8, 1), to_date=date(2024, 8, 5), adjusted=True)

# adjusted=True works for every OHLCV column: open/high/low/close divide by the
# CA factor, volume multiplies (include=(...) selects the event set, as in ohlc_adjusted)
adj_vol = data.wide_frame(column="volume", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5), adjusted=True)

# Several columns in one pass over the staged days -> {column: DataFrame}
panel = data.wide_frames(columns=["close", "volume"], symbols=["RELIANCE", "TCS"], adjusted=True)
```

```python
# Stream one validated frame per staged day (memory-bounded multi-year passes).
# Supports bhavcopy / fo_bhavcopy / full_bhavcopy / index_closes / bulk_deals / block_deals.
from powernse.datasets import BHAVCOPY

for day, frame in data.iter_days(BHAVCOPY, from_date=date(2020, 1, 1), to_date=date(2024, 12, 31)):
    ...  # frame is that day's OhlcSchema-shaped bhavcopy
```

```python
# Typed delivery / traded-value reads from the staged sec_bhavdata_full archive
deliv = data.delivery("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
day = data.delivery_on(date(2024, 8, 9))                       # every EQ row that day; series=None for all series
pct = data.delivery_frame(column="delivery_pct", symbols=["RELIANCE", "TCS"])  # Date x Symbol matrix
```

```python
# Equity security master (latest staged EQUITY_L): symbol / ISIN / name / listing date / face value
master = data.securities()                          # whole table, SecuritySchema-shaped
data.security("RELIANCE")                           # one row (Series), or None
data.security_by_isin("INE002A01018")              # reverse lookup, or None
```

Indexes — `Index("nifty50")` carries identity from a bundled catalog of every
NSE equity index (no archive needed); `data.index(name)` binds it to the staged
archive for data reads:

```python
from powernse import Index

nifty = Index("nifty50")                                # normalizes via the catalog
nifty.name, nifty.code, nifty.category, nifty.fno       # "NIFTY 50", "NIFTY 50", "broad", True
Index.catalog()                                         # every catalogued index (unbound)

# data reads need an archive:
data.indexes()                                          # index names in the latest staged file
nifty = data.index("nifty50")                           # same handle, now bound
nifty.ohlc(from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
nifty.latest()                                          # newest close row, or None
nifty.symbols(date(2024, 8, 1))                         # EQ constituents on that snapshot (needs index-constituents downloads)
nifty.constituent_dates()                              # staged snapshot dates
```

`powernse indexes` lists staged index names; `powernse indexes --known` lists the bundled catalog.

Trading calendar arithmetic:

```python
from powernse.calendar import XBOM

XBOM.sessions(date(2024, 8, 1), date(2024, 8, 31))     # list[date] of trading days
XBOM.count(date(2024, 8, 1), date(2024, 8, 31))        # how many
XBOM.offset(date(2024, 8, 1), 30)                      # the 30th session after
XBOM.is_session(date(2024, 8, 15))                     # False — Independence Day
XBOM.holidays(date(2024, 8, 1), date(2024, 8, 31))     # weekday non-sessions in the range
```

Coverage — `coverage_gaps()` is `coverage(BHAVCOPY, ...)`; `coverage(dataset, ...)`
generalizes it to any dated archive, defaulting the window to that dataset's full
staged span:

```python
from powernse.datasets import FO_BHAVCOPY

data.coverage(FO_BHAVCOPY)                             # sessions missing an F&O bhavcopy file
data.audit_manifest()                                 # [ManifestIssue(local_path, kind)] — sha256 drift / missing files
```

`powernse verify` reports the session gaps for the core dated archives from the
shell (exit 1 if any); `powernse verify --hashes` also re-hashes every staged
file against the download manifest.

Corporate actions — `data.corporate_actions(symbol, ...)` classifies each staged
record (type, subject, derived `price_factor` / `dividend_amount`) into a frame;
`actions_for(symbol, ...)` returns the untouched records:

```python
history = data.corporate_actions("RELIANCE", from_date=date(2024, 1, 1), to_date=date(2024, 8, 5))
```

For bars and records you already hold (no archive), use the classes directly:

```python
from powernse import CorporateActions, SubjectClassifier

SubjectClassifier().classify("Bonus 1:1")               # CorporateActionType.BONUS
CorporateActions(records).adjust(bars)                   # AdjustedOhlcSchema frame
CorporateActions(records).classified()                  # classified history frame
```

## What you should see

- `ohlc`, `ohlc_adjusted`, `fo_bars`, `index_ohlc`, `on` return `pandas.DataFrame` (empty
  DataFrame — same columns, zero rows — if no matches; CLI `ohlc` exits `1` when empty)
- `latest()` returns a one-row `pandas.Series`, or `None` if nothing is staged yet
- `inventory()` counts files per archive prefix
- Missing required files raise `ArchiveError`

`ohlc_adjusted` parses adjustment terms straight from the corporate-action
subject; unrecognized subjects are skipped. Dividend and rights adjustment use
the close on the prior trading day, so they need OHLC bars loaded before the CA
records.

**Adjustment scope.** The default event set for `ohlc_adjusted` /
`wide_frame(adjusted=True)` / `CorporateActions.factors` is **bonus, split,
consolidation, and dividend** — including percentage dividends (`Div 30%`,
resolved against the record's face value). Against the bundled archive that
parses ~98 % of bonus/split records and ~75 % of dividend records.

**BSE dividend backfill.** Some NSE dividend records carry no per-share figure in
their subject. Run `powernse bse-corporate-actions --from … --to …` to stage
BSE's free corporate-actions feed; once it's present, `ohlc_adjusted` /
`corporate_actions()` fill the missing amount from BSE for the same symbol and
ex-date (± 1 day). It is automatic, dividends only, and the NSE subject wins
whenever it has a number.

**Rights issues** are opt-in: pass
`include=("bonus", "split", "consolidation", "dividend", "rights")` to
`ohlc_adjusted` / `wide_frame` / `wide_frames`, or `apply={…, "rights"}` to
`CorporateActions`. The divisor is the theoretical ex-rights price from the
ratio + subscription price in the subject (~94 % of NSE rights records parse;
deep-out-of-the-money issues are left unadjusted, as NSE does).
`CorporateActions(records, apply={"rights"}).skipped_events()` lists the records
whose terms could not be read.

**Not adjusted at all:** buyback tenders (no standard ex-date price move),
demergers (need the spun-off entity's value), capital reductions and
redemptions. These stay classified by `corporate_actions()` and flagged
`price_affecting`; adjust for them out of band if a long history needs it. There
is no free, machine-readable NSE F&O adjustment-factor file, and NSE's
`corporatections.csv` is the same data as the JSON we already stage.

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
