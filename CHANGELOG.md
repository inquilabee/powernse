# Changelog

## Unreleased

### Added

- Typed delivery / traded-value reads from the staged `sec_bhavdata_full` archive: `NSEData.delivery(symbol, from_date=, to_date=, series=)` (per-symbol history — delivery qty/%, turnover, trade count, `DeliverySchema`-shaped), `NSEData.delivery_on(trade_date, symbol=, series=)` (one staged day; `series=None` for every series), `NSEData.delivery_frame(column=, symbols=, from_date=, to_date=, series=)` (Date × Symbol matrix of `delivery_pct` / `delivery_qty` / `turnover_lacs` / `volume`). `powernse.schemas` gains `DeliverySchema` / `DeliveryRow`

## 0.3.0 — 2026-08-28

### Added

- `powernse.index` package + a bundled catalog of every NSE equity index (identity only — canonical `name`, short `code`, `category` ∈ broad/sectoral/thematic/strategy/fixed_income, `fno`). `Index("nifty50")` now constructs standalone and normalizes via the catalog (`Index.catalog()`; `IndexEntry` / `IndexCatalog` / `load_entries()` / `lookup()` in `powernse.index`). Data reads still need an archive — `NSEData(root).index(name)` binds one, and unbound data calls raise a clear `ArchiveError`. `powernse indexes --known` lists the catalog. `scripts/build_index_catalog.py` regenerates `indexes.json` from NSE's `/api/allIndices`
- `Index.exists()` is offline-aware: `True` for any catalogued index; still checks the latest staged index-closes file for a non-catalogued name when bound

## 0.2.0 — 2026-08-28

Large release: pandas became the data interface, then the whole read layer was
restructured and grown into a research-grade data surface. No compatibility
shims — see the migration notes below.

### Added

- `powernse.schemas`: `OhlcSchema` / `AdjustedOhlcSchema` / `FoSchema` / `IndexSchema` ([pdschema](https://github.com/inquilabee/pdschema) `Schema` subclasses). Every DataFrame-returning method validates its result against one before returning. New dependency: `pdschema` (pulls in `pyarrow`)
- `powernse.corporate_actions`: `CorporateActions` (pure — built from records), `CorporateActionType`, `SubjectClassifier` (`classify` / `price_factor` / `dividend_amount` / `describe`). Replaces the deleted `powernse.adjust`
- `NSEData.corporate_actions(symbol, from_date=, to_date=)`: classified CA history as a DataFrame; `NSEData.actions_for(symbol, ...)` for the raw records
- `NSEData.wide_frame(column=, symbols=, from_date=, to_date=, series=, adjusted=)`: single-pass Date × Symbol matrix for one OHLCV column; `adjusted=True` applies the per-symbol bonus/split/dividend factor (`column="close"` only). `CorporateActions.factors(bars)` exposes the per-bar cumulative divisor on its own
- `powernse.Index` handle + `NSEData.indexes(on=)` / `NSEData.index(name)`: list every staged index name, then `data.index("Nifty 50").ohlc()` / `.latest()` / `.symbols(on)` / `.constituent_dates()` / `.exists()`. New `powernse indexes` CLI command
- `TradingCalendar` (in `powernse.calendar`, `XBOM` is the module singleton) with `sessions(from, to)` / `count(from, to)` / `offset(day, n)` — trading-day list, count, and the session `n` steps from a date
- `powernse.datasets` registry (`Dataset` per archive family) and `ArchiveRoot.staged_path(dataset, day)` / `staged_key` / `latest_staged_date` / `staged_dates`
- `powernse.window.DateWindow`, `powernse.archive.payloads` (`looks_like_html`, `extract_csv_from_zip`), and an internal `powernse.reading` subsystem behind the `NSEData` facade

### Changed — breaking

- Bulk reads return `pandas.DataFrame`; `NSEData.latest()` returns `pandas.Series | None`. The `OhlcBar` / `AdjustedOhlcBar` / `FoBar` / `IndexBar` dataclasses are removed, as is `NSEData.ohlc_frame()` (use `ohlc()`)
- `CorporateActions` is constructed from records, not an archive: `CorporateActions(records).classified()` / `.price_events(bars)` / `.adjust(bars)`. `CorporateActions(archive)`, `.frame()`, `.apply()`, `.adjusted_ohlc()` are gone — use `NSEData.corporate_actions()` / `NSEData.ohlc_adjusted()`. `price_events()` returns a `pandas.Series`
- `classify_subject()` / `price_adjustment_factor_from_subject()` / `dividend_amount_from_subject()` → methods on `SubjectClassifier` (`SUBJECTS` is the default instance)
- `NSEData.index_ohlc()` / `index_symbols()` removed — use `NSEData.index(name).ohlc()` / `.symbols(on)`. `NSEData.bhavcopy_rows()` removed (use `on()`); `bhavcopy_frame()` and `latest_full_bhavcopy_date()` removed
- `powernse.calendar.is_weekend` / `calendar_session_bounds` → `TradingCalendar` (`iter_trading_dates` unchanged)
- Downloaders: the per-archive `*_archive_url` / `staged_*_csv_path` / `staged_*_csv_key` / `latest_staged_*_date` / `resolve_*_resume_range` module functions are gone. Remote URLs are `@staticmethod archive_url` / `request_url` on each downloader; staged paths go through `ArchiveRoot` + `powernse.datasets`; `resolve_dated_resume_range(root, dataset, ...)` takes a `Dataset`
- `powernse.archive.extract_zip_payload_to_csv_bytes` → `powernse.archive.payloads.extract_csv_from_zip`; `powernse.http` no longer re-exports `looks_like_html`
- Every downloader shares one `ArchiveDownloader.__init__`; a hand-built `Settings(sleep_seconds=…)` / `Settings(skip_existing=…)` passed as the `root` argument to a dated/snapshot downloader is now honoured (previously ignored by those subclasses)

### Fixed

- `NSEData.ohlc_adjusted()` no longer applies a corporate action to the whole loaded bar range when its ex-date falls after the newest bar (an announced-but-not-yet-effective bonus/split/dividend) — such events are dropped instead of retroactively adjusting earlier bars

### Internal

- The cumulative-adjustment-factor walk is a vectorized pandas/numpy computation (`searchsorted` into a suffix cumulative-product of sorted events)
- `NSEData` is a ~170-line facade over five `powernse.reading` collaborators; `parsers.rows` is a `RowParser[RowT]` Template Method; `bundle.py` folded into `BundleFetcher`; the `data ↔ corporate_actions` import cycle removed
- ShipGate `--suite full` (25 checks) is the enforced gate; the `.shipgate/` policy subset is versioned and the suite runs sequentially

## 0.1.3 — 2026-08-25

### Added

- `dividend_amount_from_subject`, `corporate_action_dividend_events`, and `dividend_price_events` in `powernse.adjust` — dividend price adjustment, previously entirely absent despite dividend records already being downloaded and retrievable via `NSEData.actions_for()`. Convert into the same `(ex_date, divisor)` shape `apply_price_adjustments` already consumes, so no change was needed there
- Workflow `release-nse-data.yml` publishes Release asset `nse-data.zip` (tag `nse-data-bundle`)

### Fixed

- `SPLIT_TO_FROM` now recognizes `Re` (not just `Rs`) for the face-value amount, so splits down to exactly ₹1 (e.g. "From Rs 10/- Per Share To Re 1/- Per Share") are no longer silently left unadjusted

### Removed

- `ArchiveReader` compatibility alias for `NSEData` — use `NSEData` directly

### Changed

- Download CLI exits `1` on `failed` days only with `--strict` (default soft-fail); refresh workflow passes `--strict`
- `ohlc_adjusted` loads CA JSON by file stem in a capped lookback before the OHLC window (not an unbounded calendar walk)
- Package front no longer re-exports `bhavcopy_archive_url` (import from `powernse.downloaders`)

## 0.1.1 — 2026-08-15

### Changed

- `pandas` is a core install dependency (no more `powernse[pandas]` extra); `ohlc_frame` / `bhavcopy_frame` import pandas directly

## 0.1.0 — 2026-08-15

### Added

- CLI (`powernse`) for CM / F&O / full bhavcopy, index closes, bulk/block deals, F&O sec-ban, corporate-actions, index-constituents, `fetch-bundle`, status, `ohlc` / `ohlc-adjusted` / `fo-ohlc` / `index-ohlc`, and doctor
- `--resume` / `--days` for dated archive series (empty archives clamp to today-minus `--days`; pass `--from` to uncapped)
- Python API: `NSEData`, `OhlcBar`, `AdjustedOhlcBar`, `FoBar`, `IndexBar`, and downloaders including deals / F&O / full / index closes
- `ArchiveReader` compatibility alias for `NSEData` (prefer `NSEData`)
- GitHub `nse-data/` zipball extract (`fetch-bundle`); optional Release asset via `--url`
- Local archive layout with SHA-256 download manifest
- DataFrame helpers (`ohlc_frame`, `bhavcopy_frame`) via pandas
- Weekly GitHub Actions refresh workflow for the tracked `nse-data/` tree
- ShipGate quality gates (`make check` / `make format`) and tag-triggered PyPI publish workflow
- MkDocs Material docs site at <https://inquilabee.github.io/powernse/>

### Fixed

- Trading-date iteration no longer raises when `--from` is before XBOM coverage in `exchange-calendars` (weekdays before 2006-08-16; XBOM sessions inside coverage)
