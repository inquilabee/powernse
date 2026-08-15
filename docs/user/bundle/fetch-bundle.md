# Fetch the GitHub nse-data bundle

Download the tracked `nse-data/` directory from this project's GitHub repo as a zip and extract it locally — without cloning history.

## Try this

```bash
# Set once (required unless the installed package declares [project.urls] Repository)
export POWERNSE_GITHUB_REPO=OWNER/REPO
# optional: export POWERNSE_GITHUB_BRANCH=main

powernse fetch-bundle --force
powernse status
```

Or pass flags:

```bash
powernse fetch-bundle --repo OWNER/REPO --branch main --dest ./nse-data --force
```

Direct zipball or **Release asset** URL (overrides repo/branch; prefer a `nse-data.zip` Release when the code tree is large):

```bash
powernse fetch-bundle --url 'https://codeload.github.com/OWNER/REPO/zip/refs/heads/main' --force
powernse fetch-bundle --url 'https://github.com/OWNER/REPO/releases/download/TAG/nse-data.zip' --force
```

## What you should see

```text
fetch-bundle: wrote 42 files to /…/nse-data
```

- Destination defaults to `./nse-data` or `POWERNSE_ROOT`
- `--force` **replaces** the destination tree (orphans from older layouts are removed)
- Without `--force`, a non-empty destination raises an error
- The zip must contain an `nse-data/` folder
- If GitHub only has placeholder `.gitkeep` files, download from NSE instead

## Sunday updates

Maintainers refresh official downloads into `nse-data/` on GitHub (weekly workflow). After that commit lands, clients re-run `fetch-bundle --force` to sync.

## Next

- [Quickstart](../quickstart.md)
- [Download from NSE](../download/archives.md)
