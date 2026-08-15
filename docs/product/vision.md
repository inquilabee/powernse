# Vision

## Who

Python developers and market data users who need official NSE India equity end-of-day archives on disk, then load them from a CLI or a few Python calls.

## Product

PowerNSE (`powernse`) downloads and stages official NSE CM bhavcopy files, corporate actions JSON, and index constituent snapshots under a local archive root. It exposes one CLI (`powernse`) and a small package-front API for download and read.

## Not this

Not a live quote or option-chain terminal. Not a broker. Not a strategy lab. Not a Kaggle or third-party dump ingest tool — those are optional user shortcuts documented only as external tips.

## Success

A user can `pip install powernse`, download a date range of bhavcopy into `./nse-data`, run `powernse status`, and load rows or a DataFrame from Python without hunting NSE URL formats.
