# Changelog

## 0.1.0 — 2026-08-15

### Added

- CLI (`powernse`) for bhavcopy (including `--resume` / `--days`), corporate-actions, index-constituents, status, ohlc, and doctor
- Python API: `NSEData`, `OhlcBar`, `BhavcopyDownloader`, `CorporateActionsDownloader`, `IndexConstituentsDownloader`
- `ArchiveReader` compatibility alias for `NSEData`
- Local archive layout with SHA-256 download manifest
- Optional `powernse[pandas]` DataFrame helpers (`ohlc_frame`, `bhavcopy_frame`)
