# NSE data archive

Tracked end-of-day archives refreshed from NSE exchange sources.

CM bhavcopy on this tree runs from **1994-11-03** (when NSE equity archives begin
hosting files) through the latest staged session. Weekdays before that, and
calendar gaps that return HTTP 404 from `nsearchives.nseindia.com`, are not
available from the exchange. Other series folders may still be empty placeholders
until a refresh fills them.

This tree may start with layout placeholders (`.gitkeep`) only. CSV/JSON payloads are added by the Sunday GitHub Actions refresh (or by maintainers running `powernse … --root ./nse-data` and committing). Until those files exist on GitHub, `fetch-bundle` will not yield OHLC bars — download from NSE locally instead.

A large local history under this directory can be `git add`ed when you are ready to publish; ~hundreds of MB is normal for multi-year CM bhavcopy.

## Layout

```text
raw/bhavcopy/
raw/fo_bhavcopy/
raw/full_bhavcopy/
raw/index_closes/
raw/bulk_deals/
raw/block_deals/
raw/fo_secban/
raw/corporate_actions/
raw/index_constituents/
manifest/
```

## Get a copy without cloning the whole repo

```bash
powernse fetch-bundle --force
# or
powernse fetch-bundle --repo inquilabee/powernse --dest ./nse-data --force
export POWERNSE_GITHUB_REPO=inquilabee/powernse
```

Prefer a Release asset (`--url …/nse-data.zip`) when the code repository is large.

## Sunday refresh

Workflow `.github/workflows/refresh-nse-data.yml` resumes downloads (including corporate-actions and index-constituents) and commits updates. Locally:

```bash
powernse bhavcopy --resume --days 14 --root ./nse-data
powernse fo-bhavcopy --resume --days 14 --root ./nse-data
powernse index-closes --resume --days 14 --root ./nse-data
powernse full-bhavcopy --resume --days 14 --root ./nse-data
powernse corporate-actions --from "$(date -u -d '14 days ago' +%F)" --to "$(date -u +%F)" --root ./nse-data
powernse index-constituents --label-date "$(date -u +%F)" --root ./nse-data
powernse bulk-deals --date "$(date -u +%F)" --root ./nse-data
powernse block-deals --date "$(date -u +%F)" --root ./nse-data
powernse fo-secban --date "$(date -u +%F)" --root ./nse-data
```
