# Changelog

## Unreleased

### Added

- `powernse.corporate_actions` module: `CorporateActions` class (classification + `frame()` + `adjusted_ohlc()`), `CorporateActionType`, `classify_subject()`. Replaces `powernse.adjust` (deleted, no compatibility shim). Top-level exports: `from powernse import CorporateActions, CorporateActionType`
- `NSEData.wide_frame()`: Date x Symbol matrix for one OHLCV column, read across staged bhavcopy days in a single pass (values are unadjusted)
- `powernse.SubjectClassifier`: the CA-subject reader (`classify` / `price_factor` / `dividend_amount` / `describe`), extracted from the loose `classify_subject()` / `*_from_subject()` functions
- `NSEData.corporate_actions(symbol, from_date=, to_date=)`: classified CA history as a DataFrame; `NSEData.actions_for(symbol, ...)` for the unclassified records
- `powernse.Index` handle + `NSEData.indexes(on=)` / `NSEData.index(name)`: list every staged index name, then `data.index("Nifty 50").ohlc()` / `.latest()` / `.symbols(on)` / `.constituent_dates()` / `.exists()`. Replaces the flat `NSEData.index_ohlc()` / `index_symbols()`
- `NSEData.wide_frame(..., adjusted=True)`: Date x Symbol *adjusted*-close matrix (per-symbol bonus/split/dividend factor, `column="close"` only); `CorporateActions.factors(bars)` exposes the per-bar cumulative divisor on its own
- `TradingCalendar.sessions(from, to)` / `count(from, to)` / `offset(day, n)`: trading-day list, count, and the session `n` steps from a date

### Changed — breaking (structure)

Internal reshape; the `NSEData` + downloaders + `Settings`/errors surface is otherwise unchanged.

- `CorporateActions` is constructed from records, not an archive: `CorporateActions(records).classified()` / `.price_events(bars)` / `.adjust(bars)`. `CorporateActions(archive)`, `.frame()`, `.apply()`, `.adjusted_ohlc()` are gone — use `NSEData.corporate_actions()` / `NSEData.ohlc_adjusted()` for the archive-backed path
- `classify_subject()`, `price_adjustment_factor_from_subject()`, `dividend_amount_from_subject()` → methods on `SubjectClassifier` (`SUBJECTS` is the default instance)
- `NSEData.bhavcopy_rows()` removed (use `on()` for a typed frame); `bhavcopy_frame()` and `latest_full_bhavcopy_date()` removed (unused)
- `NSEData.index_ohlc()` / `index_symbols()` removed -- use `NSEData.index(name).ohlc()` / `.symbols(on)`
- `powernse.calendar.is_weekend` / `calendar_session_bounds` → `TradingCalendar` (`XBOM` is the module singleton; `iter_trading_dates` unchanged)
- Downloaders: the per-archive `*_archive_url` / `staged_*_csv_path` / `staged_*_csv_key` / `latest_staged_*_date` / `resolve_*_resume_range` module functions are gone. Remote URLs are `@staticmethod archive_url` / `request_url` on each downloader; staged paths are `ArchiveRoot.staged_path(dataset, day)` via the new `powernse.datasets` registry; resume windows are `resolve_dated_resume_range(root, dataset, ...)`
- `powernse.archive.extract_zip_payload_to_csv_bytes` → `extract_csv_from_zip` (in the new `powernse.archive.payloads`, with `looks_like_html`); `powernse.http` no longer re-exports `looks_like_html`
- Every downloader now shares one `ArchiveDownloader.__init__`. A hand-built `Settings(sleep_seconds=…)` / `Settings(skip_existing=…)` passed as the `root` argument to a dated or snapshot downloader is now honoured (previously silently ignored by those subclasses)

### Changed — breaking

pandas is now the core interface, not a bolt-on:

- `NSEData.ohlc()`, `NSEData.on()`, `NSEData.fo_bars()`, `NSEData.index_ohlc()`, `NSEData.ohlc_adjusted()`, and `CorporateActions.adjusted_ohlc()` / `CorporateActions.apply()` now return `pandas.DataFrame` instead of `list[OhlcBar]` / `list[AdjustedOhlcBar]` / `list[FoBar]` / `list[IndexBar]`. `NSEData.ohlc_frame()` is removed — `ohlc()` is now the one method (same for the other `_frame`-suffixed siblings, which never existed for these)
- `NSEData.latest()` returns `pandas.Series | None` (one OHLC row) instead of `OhlcBar | None`
- `OhlcBar`, `AdjustedOhlcBar`, `FoBar`, and `IndexBar` are removed entirely — no compatibility shim. `CorporateActions.price_events()` returns a `pandas.Series` (ex-date index, multiplier values) instead of `list[tuple[date, float]]`, and its `bars` parameter (like `apply()`'s) is now a DataFrame instead of `list[OhlcBar]`
- Added `powernse.schemas`: `OhlcSchema`, `AdjustedOhlcSchema`, `FoSchema`, `IndexSchema` ([pdschema](https://github.com/inquilabee/pdschema) `Schema` subclasses) take over the type/nullability contract the four dataclasses used to enforce, validated at the point each method returns its DataFrame. New dependency: `pdschema` (pulls in `pyarrow` transitively)
- `CorporateActions._apply_adjustments`'s cumulative-adjustment-factor walk is rewritten as a vectorized pandas/numpy computation (`searchsorted` into a suffix cumulative-product of sorted events) instead of a manual event-index-walking loop over dataclass instances

### Fixed

- `CorporateActions.apply()` / `NSEData.ohlc_adjusted()` no longer apply a corporate action to the entire loaded bar range when its ex-date falls after the newest bar (e.g. an announced-but-not-yet-effective bonus/split/dividend) — such events are now dropped instead of retroactively adjusting bars that predate the action taking effect

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
