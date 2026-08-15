# NSE data archive

Tracked end-of-day archives refreshed from official NSE sources.

CSV/JSON payloads are meant to live in this tree and be updated on GitHub (typically Sundays). A large local history is fine to `git add` when you are ready to publish; this repository may also start with an empty layout and grow via the weekly workflow.


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
powernse fetch-bundle --repo OWNER/REPO --dest ./nse-data
# or
export POWERNSE_GITHUB_REPO=OWNER/REPO
powernse fetch-bundle --force
```

## Sunday refresh

A GitHub Actions workflow runs weekly (`refresh-nse-data.yml`) to resume downloads into this tree and commit updates. You can also run locally:

```bash
powernse bhavcopy --resume --days 14 --root ./nse-data
powernse fo-bhavcopy --resume --days 14 --root ./nse-data
powernse index-closes --resume --days 14 --root ./nse-data
powernse full-bhavcopy --resume --days 14 --root ./nse-data
powernse bulk-deals --date "$(date -I)" --root ./nse-data
powernse block-deals --date "$(date -I)" --root ./nse-data
powernse fo-secban --date "$(date -I)" --root ./nse-data
```
