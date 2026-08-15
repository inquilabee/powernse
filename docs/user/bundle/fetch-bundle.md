# Fetch the GitHub nse-data bundle

Download the tracked `nse-data/` directory from this project's GitHub repo as a zip and extract it locally — without cloning history.

## Try this

```bash
# Set once
export POWERNSE_GITHUB_REPO=OWNER/REPO
# optional: export POWERNSE_GITHUB_BRANCH=main

powernse fetch-bundle --force
powernse status
```

Or pass flags:

```bash
powernse fetch-bundle --repo OWNER/REPO --branch main --dest ./nse-data --force
```

Direct zipball URL (overrides repo/branch):

```bash
powernse fetch-bundle --url 'https://codeload.github.com/OWNER/REPO/zip/refs/heads/main' --force
```

## What you should see

```text
fetch-bundle: wrote 42 files to /…/nse-data
```

- Destination defaults to `./nse-data` or `POWERNSE_ROOT`
- Without `--force`, a non-empty destination raises an error
- The zip must contain an `nse-data/` folder (as published in the repo)

## Sunday updates

Maintainers refresh official downloads into `nse-data/` on GitHub (weekly workflow `refresh-nse-data.yml`). After that commit lands, clients re-run `fetch-bundle --force` to sync.

## Next

- [Quickstart](../quickstart.md)
- [Download from NSE](../download/archives.md)
