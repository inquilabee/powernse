# Fetch the GitHub nse-data bundle

Download the tracked `nse-data/` directory without cloning the full git history.

## Preferred: Release asset

When the repo ships a Release named **`nse-data-bundle`** (workflow
`release-nse-data.yml`), prefer that zip — much smaller than a whole-repo zipball:

```bash
powernse fetch-bundle --force --url \
  'https://github.com/inquilabee/powernse/releases/download/nse-data-bundle/nse-data.zip'
powernse status
```

Maintainers: run **Actions → Release nse-data bundle → Run workflow** (or wait for the
Sunday schedule after the archive refresh).

## Fallback: repo zipball / metadata

```bash
# PyPI / wheel installs already know the Repository URL — no env needed
powernse fetch-bundle --force
powernse status
```

Override when needed:

```bash
export POWERNSE_GITHUB_REPO=inquilabee/powernse
# optional: export POWERNSE_GITHUB_BRANCH=main

powernse fetch-bundle --repo inquilabee/powernse --branch main --dest ./nse-data --force
```

Other URLs:

```bash
powernse fetch-bundle --url 'https://codeload.github.com/inquilabee/powernse/zip/refs/heads/main' --force
```

## What you should see

```text
fetch-bundle: wrote 42 files to /…/nse-data
```

- Bundled index-close history spans ~**1995** → present for the major indices
  (`index-history` fills the pre-2012 tail); CM bhavcopy and the rest run 2012+
- Destination defaults to `./nse-data` or `POWERNSE_ROOT`
- `--force` **replaces** the destination tree (orphans from older layouts are removed)
- Without `--force`, a non-empty destination raises an error
- The zip must contain an `nse-data/` folder
- If GitHub only has placeholder `.gitkeep` files, download from NSE instead

## Sunday updates

Maintainers refresh exchange downloads into `nse-data/` on GitHub (weekly workflow), then
the bundle Release workflow refreshes `nse-data.zip`. Clients re-run `fetch-bundle --force`
(preferably with the Release `--url`) to sync.

## Next

- [Install](../install.md)
- [Quickstart](../quickstart.md)
- [Download from NSE](../download/archives.md)
