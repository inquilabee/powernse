# Changelog

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
- MkDocs Material docs site at https://inquilabee.github.io/powernse/

### Fixed

- Trading-date iteration no longer raises when `--from` is before XBOM coverage in `exchange-calendars` (weekdays before 2006-08-16; XBOM sessions inside coverage)
