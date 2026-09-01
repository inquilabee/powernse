# Changelog

## Unreleased

### Fixed

- **`index-history` staged a near-weekly series before ~2012.** NSE's
  `indicesHistory` endpoint silently caps a response at ~70 rows however wide the
  requested window, so the 365-day chunks came back at roughly one session a week
  and a default backfill left whole quarters missing — unusable on a daily grid
  (a 200-DMA, calendar rules, dip triggers). `INDEX_HISTORY_MAX_CHUNK_DAYS` is now
  90 (~62 sessions, under the cap), so a pull stages every trading day; a full
  `index-history --all` now takes ~15 min rather than ~2. Re-run `powernse
  index-history` (add `--no-skip-existing`) to densify an archive an earlier
  version staged. `powernse/constants.py`

## 0.6.1 — 2026-09-01

### Added

- Historical-name aliases for 18 more indices now that `index-history` has staged their pre-rename data — the `CNX Auto/Energy/FMCG/Finance/Media/Metal/Pharma/PSU Bank/Realty/MNC/PSE/Service Sector/Commodities/Consumption/Infrastructure/Dividend Opportunities` series and `CNX Smallcap` / `CNX Nifty Dividend`. `NSEData(root).index("NIFTY PHARMA").ohlc(from_date=date(2001, 1, 1), …)` (and the other sectoral / thematic names) now returns the full series across NSE's 2015 `CNX → NIFTY` rebrand instead of truncating at it. `powernse/index/aliases.py`

## 0.6.0 — 2026-09-01

### Added

- **`powernse index-history`** — one command for deep index history. Pulls per-index end-of-day levels back to the Nifty 50 base date (1995-11-03) from NSE's historical API (`/api/historicalOR/indicesHistory`), with a NSE Indices Ltd (`niftyindices.com`) fallback for the leading gap when NSE's series starts late, and merges the result into the same `raw/index_closes/YYYY/YYYY-MM-DD.csv` files `index-closes` writes. No new dataset or read path — `NSEData(root).index("NIFTY 50").ohlc(from_date=date(1995, 11, 3), …)` returns one continuous series across NSE's renames. Defaults to 24 long-history indices over `[1995-11-03, 2012-02-20]` (the tail `ind_close_all` can't reach); `--index` (repeatable), `--all`, `--from`, `--to` override. The weekly `refresh-nse-data` workflow runs it, so the published `nse-data/` bundle now carries index history back to ~1995 for the major indices. New `IndexHistoryDownloader` / `HistoricalIndexSource` / `NseIndicesHistorySource` / `NiftyIndicesHistorySource`; `NseHttpClient.post_bytes`

## 0.5.0 — 2026-09-01

### Added

- **Historical index-name aliases.** `NSEData(root).index("NIFTY 50").ohlc(...)` now returns the continuous series across NSE's renames — the staged `ind_close_all` files carry whichever name was current on that date (`S&P CNX Nifty` → `CNX Nifty` → `Nifty 50`, `Bank Nifty` → `Nifty Bank`, `CNX IT` → `Nifty IT`, …). `IndexEntry.aliases`; an old name resolves too (`index("CNX Nifty").known` is `True`, `.name` is `"NIFTY 50"`). Map curated in `powernse/index/aliases.py` (#4)
- **`powernse index-closes --backfill`** (and on the other dated download commands): fetch the history *before* the earliest staged file, from the source's known start — the leading gap `--resume` (forward-only) can't reach. `Dataset.history_start`; index closes start `2012-02-21` (`ind_close_all` 404s before that). Soft-exits with "nothing to backfill" once the history is staged. The published `nse-data/` bundle now ships index-close history back to 2012-02, like bhavcopy (#5)
- **`powernse --version`** prints the installed version (#5)
- **Opt-in on-disk cache for adjusted wide-frame reads.** `NSEData(root, cache_dir=…)` (or `POWERNSE_CACHE_DIR`) memoises `wide_frame(adjusted=True)` / `wide_frames(adjusted=True)` results to disk, keyed by the request plus the latest staged bhavcopy day so a refresh invalidates it. `wide_frame` / `wide_frames` gain `cache: bool = True`. `powernse.reading.WideFrameCache` (#3)

## 0.4.1 — 2026-08-30

### Added

- `NSEData.price_anomalies(symbol, from_date=, to_date=, threshold=0.4, series=) -> list[PriceAnomaly]` and `powernse anomalies SYMBOL`: flag one-day close moves past a threshold and tag each with the corporate action that explains it. `ca_type is None` is a **suspected unadjusted action** — NSE's equity CA feed omits ETF unit splits (NIFTYBEES / BANKBEES / GOLDBEES all split 1:10 on 2019-12-19 with no feed record), so `ohlc_adjusted` silently leaves those raw jumps in. `PriceAnomaly` exported from `powernse`; CLI exits 1 on any unexplained move

### Fixed

- `NSEData.bulk_deals()` / `block_deals()` (and `iter_days(BULK_DEALS/BLOCK_DEALS)`) now read the label-dated snapshot files and filter by the parsed `Date` column, instead of iterating trading sessions. Deal files downloaded on a weekend (or any day after the trade date) carry the prior session's rows — the old reader looked for a file named after the trading day and returned nothing, so every Sunday `Refresh nse-data` staged deals that were invisible to the API
- Weekly `refresh-nse-data` workflow: `index-constituents` option is `--date`, not the pre-0.2 `--label-date`

## 0.4.0 — 2026-08-29

### Added

- Corporate-action adjustment now also covers **percentage dividends** (`Div 30%` → `face_value × 30 %` per share, via `faceVal` in the record) and **share consolidations** (`Consolidation From Re 1 To Rs 10` → reverse-split divisor), in the default set alongside bonus / split / dividend. `SubjectClassifier.dividend_amount(subject, face_value=)` and `SubjectClassifier.consolidation_factor(subject)`; `corporate_actions.face_value_of()`. Lifts the staged-archive dividend parse rate from ~55 % to ~75 %
- **Opt-in rights-issue adjustment**: `NSEData.ohlc_adjusted(..., include=("bonus","split","consolidation","dividend","rights"))` (and the same `include=` on `wide_frame` / `wide_frames`, or `apply={…,"rights"}` on `CorporateActions`) applies the theoretical ex-rights price from the ratio + subscription price in the subject (~94 % of NSE rights records parse; deep-OTM issues left unadjusted). `SubjectClassifier.rights_terms(subject, face_value=) -> RightsTerms | None`; `CorporateActions.skipped_events() -> list[SkippedEvent]` lists price-affecting records whose terms could not be read. `RightsTerms` / `SkippedEvent` exported from `powernse`
- `scripts/ca_coverage.py`: maintainer tool that reports per-type CA adjustment coverage against the staged archive (and, with `--with-bse`, the staged-BSE dividend backfill delta)
- BSE dividend cross-check: `powernse bse-corporate-actions --from --to` stages BSE's free corporate-actions feed (`bse_corporate_actions` dataset, one JSON per ex-date). Once present, `NSEData.ohlc_adjusted` / `corporate_actions()` backfill a dividend amount from BSE — same symbol, ex-date ± 1 day — when the NSE subject carries none. Automatic, dividends only, NSE subject wins. The measured lift is small (BSE's amounts mostly overlap what NSE already states), but it fills genuine "Dividend / no figure" gaps. New `BseCorporateActionsDownloader` / `powernse.reading.BseCorporateActionReader`; `powernse.parsers.parse_bse_dividend`; `NseHttpClient.fetch_bytes(extra_headers=)`
- Typed delivery / traded-value reads from the staged `sec_bhavdata_full` archive: `NSEData.delivery(symbol, from_date=, to_date=, series=)` (per-symbol history — delivery qty/%, turnover, trade count, `DeliverySchema`-shaped), `NSEData.delivery_on(trade_date, symbol=, series=)` (one staged day; `series=None` for every series), `NSEData.delivery_frame(column=, symbols=, from_date=, to_date=, series=)` (Date × Symbol matrix of `delivery_pct` / `delivery_qty` / `turnover_lacs` / `volume`). `powernse.schemas` gains `DeliverySchema` / `DeliveryRow`
- Typed bulk / block deal reads: `NSEData.bulk_deals(from_date=, to_date=, symbol=, side=)` and `NSEData.block_deals(...)` return a `DealSchema`-shaped DataFrame across the staged window, filterable by symbol and buy/sell side. `powernse.schemas` gains `DealSchema` / `DealRow`
- F&O securities-in-ban reads: `NSEData.secban(on=None) -> set[str]` and `NSEData.is_banned(symbol, on=None) -> bool`, keyed by the effective trade date parsed from each `fo_secban` file's header (`on=None` → the latest staged ban date). `powernse.parsers.parse_secban(text)` exposes the parse
- Equity security master: `powernse equity-list` downloads NSE's `EQUITY_L.csv`; `NSEData.securities() -> DataFrame` (whole master, `SecuritySchema`: symbol / name / series / listing_date / paid_up_value / market_lot / isin / face_value), `NSEData.security(symbol)` / `NSEData.security_by_isin(isin) -> Series | None`, and a `powernse securities [--symbol | --isin]` read command. New `EquityListDownloader`, `powernse.schemas.SecuritySchema` / `SecurityRow`, `equity_list` dataset
- `NSEData.coverage(dataset, from_date=, to_date=) -> list[date]`: session gaps for any dated archive; the window defaults to that dataset's full staged span. `NSEData.coverage_gaps()` is now `coverage(BHAVCOPY, ...)`
- `TradingCalendar.is_session(day) -> bool` and `TradingCalendar.holidays(from_date, to_date) -> list[date]` (weekday non-sessions in the range)
- `NSEData.wide_frames(columns=[...], symbols=, from_date=, to_date=, series=, adjusted=) -> dict[str, DataFrame]`: one Date × Symbol matrix per column, sharing a single pass over the staged days
- `NSEData.wide_frame(adjusted=True)` now works for every OHLCV column, not just close — open/high/low/close divide by the per-symbol bonus/split/dividend factor, `volume` multiplies (the old `adjusted=True` + non-close `ValueError` is gone)
- `NSEData.iter_days(dataset, from_date=, to_date=) -> Iterator[(date, DataFrame)]`: stream one validated frame per staged day for memory-bounded multi-year passes (bhavcopy / F&O bhavcopy / full bhavcopy / index closes / bulk / block deals)
- `powernse verify [--dataset KEY] [--from] [--to] [--hashes]`: reports staged-session gaps for the core dated archives (bhavcopy / F&O bhavcopy / index closes / full bhavcopy); `--hashes` also re-hashes every staged file against the `sha256` recorded per download in `manifest/downloads.jsonl`. `NSEData.audit_manifest() -> list[ManifestIssue]` exposes the audit. Exit 1 on any problem

### Changed — breaking

- `NSEData.bulk_deals()` / `block_deals()` are now keyword-only window reads returning a DataFrame — the old `bulk_deals(label_date) -> list[dict]` / `block_deals(label_date)` / `fo_secban(label_date)` raw-CSV forms are removed (`fo_secban` is replaced by `secban()` / `is_banned()`). `full_bhavcopy_rows()` is unchanged
- `NSEData.coverage_gaps()` with no `from_date` / `to_date` now scans the full staged bhavcopy span instead of only the latest staged day

### Docs

- Rewrote the "Adjustment scope" section: default event set (bonus / split / consolidation / dividend), opt-in rights, and what stays unadjusted (buyback / demerger / capital reduction) and why — plus the finding that no free machine-readable NSE F&O adjustment-factor file exists and `corporatections.csv` is the same data as the JSON already staged

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
