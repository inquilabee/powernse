# Vision

## Who

Python developers and market data users who need official NSE India end-of-day archives on disk, then load them from a CLI or a few Python calls.

## Product

PowerNSE (`powernse`) downloads and stages official NSE cash and F&O archives (bhavcopy, full bhavcopy, index closes, deals snapshots), corporate actions, and index constituents under a local archive root. It can also fetch a GitHub-hosted `nse-data/` tree as a zip. One CLI (`powernse`) and a small package-front API (`NSEData`) cover download and read.

## Not this

Not a live quote or option-chain terminal. Not a broker. Not a strategy lab. Not a Kaggle or third-party dump ingest tool — those are optional user shortcuts documented only as external tips.

## Success

A user can `pip install powernse`, either `fetch-bundle` a published archive or download a date range from NSE into `./nse-data`, run `powernse status` / `ohlc`, and load bars from Python without hunting NSE URL formats.
