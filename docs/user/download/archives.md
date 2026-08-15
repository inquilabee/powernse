# Download archives

Pull official NSE end-of-day files into a local archive root.

## Try this

```bash
# Cash-market bhavcopy
# --resume: last staged → today; empty archives clamp to today-minus --days (default 100)
powernse bhavcopy --resume
powernse bhavcopy --resume --days 30
powernse bhavcopy --resume --from 2000-01-01   # uncapped history
powernse bhavcopy --from 2024-08-01 --to 2024-08-05

# F&O bhavcopy, index closes, full bhav (delivery columns)
powernse fo-bhavcopy --from 2024-08-01 --to 2024-08-05
powernse index-closes --from 2024-08-01 --to 2024-08-05
powernse full-bhavcopy --from 2024-08-01 --to 2024-08-05

# Snapshots (as-of download time; --date only names the file)
powernse bulk-deals --date 2024-08-09
powernse block-deals --date 2024-08-09
powernse fo-secban --date 2024-08-09

powernse corporate-actions --from 2024-08-01 --to 2024-08-05
powernse index-constituents --index "NIFTY 50" --label-date 2024-08-05
```

## What you should see

```text
bhavcopy: downloaded=3 skipped=0 failed=0 root=/…/nse-data
```

- `downloaded` — new files written
- `skipped` — already present (`--skip-existing` default)
- `failed` — missing days or HTTP/HTML responses (exit `1` if any)

Default date walking uses the XBOM calendar. Use `--all-calendar-days` only when you intentionally want weekends/holidays.

## Where files land

```text
nse-data/
  raw/bhavcopy/YYYY/YYYY-MM-DD.csv
  raw/fo_bhavcopy/YYYY/YYYY-MM-DD.csv
  raw/full_bhavcopy/YYYY/YYYY-MM-DD.csv
  raw/index_closes/YYYY/YYYY-MM-DD.csv
  raw/bulk_deals/YYYY/YYYY-MM-DD.csv
  raw/block_deals/YYYY/YYYY-MM-DD.csv
  raw/fo_secban/YYYY/YYYY-MM-DD.csv
  raw/corporate_actions/YYYY/YYYY-MM-DD.json
  raw/index_constituents/YYYY/YYYY-MM-DD_<index>.json
  manifest/downloads.jsonl
```

## Next

- [Python NSEData](../python/nsedata.md)
- [GitHub bundle](../bundle/fetch-bundle.md)
