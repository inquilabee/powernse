"""fetch-bundle CLI command."""

from pathlib import Path
from typing import Annotated

import typer

from powernse.bundle import BundleFetcher
from powernse.settings import Settings


def register_bundle_commands(app: typer.Typer) -> None:
    @app.command("fetch-bundle")
    def fetch_bundle_cmd(
        repo: Annotated[
            str | None,
            typer.Option(help="GitHub owner/repo hosting nse-data (or POWERNSE_GITHUB_REPO / package URLs)"),
        ] = None,
        branch: Annotated[str | None, typer.Option(help="Git branch (default: main / POWERNSE_GITHUB_BRANCH)")] = None,
        url: Annotated[
            str | None,
            typer.Option(help="Direct zipball or Release asset URL (overrides --repo/--branch)"),
        ] = None,
        dest: Annotated[
            Path | None,
            typer.Option(help="Extract destination (default: POWERNSE_ROOT or ./nse-data)"),
        ] = None,
        force: Annotated[bool, typer.Option("--force", help="Replace destination tree entirely")] = False,
    ) -> None:
        """Download the tracked nse-data/ tree from GitHub as a zip and extract it."""
        settings = Settings.resolve(dest)
        resolved_repo = repo or settings.github_repo or BundleFetcher.repo_from_package_metadata()
        resolved_branch = branch or settings.github_branch
        written = BundleFetcher().download_to(
            settings.archive_root,
            repo=resolved_repo,
            branch=resolved_branch,
            url=url,
            force=force,
        )
        typer.echo(f"fetch-bundle: wrote {written} files to {settings.archive_root}")
