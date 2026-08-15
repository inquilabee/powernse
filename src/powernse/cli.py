"""Command-line interface for PowerNSE."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from powernse.constants import DEFAULT_INDEX_NAMES, DEFAULT_SLEEP_SECONDS
from powernse.downloaders import BhavcopyDownloader, CorporateActionsDownloader, IndexConstituentsDownloader
from powernse.errors import PowerNseError
from powernse.http import NseHttpClient
from powernse.loaders import ArchiveReader
from powernse.settings import Settings


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def add_root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Archive root (default: POWERNSE_ROOT env or ./nse-data)",
    )


def add_common_download_args(parser: argparse.ArgumentParser) -> None:
    add_root_arg(parser)
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip dates/files that already exist (default: true)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="Extra sleep seconds between successful downloads",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="powernse",
        description="Download and use official NSE India equity archives.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    bhav = sub.add_parser("bhavcopy", help="Download CM bhavcopy CSV archives")
    bhav.add_argument("--from", dest="from_date", required=True, type=parse_date, help="Start date YYYY-MM-DD")
    bhav.add_argument("--to", dest="to_date", required=True, type=parse_date, help="End date YYYY-MM-DD")
    add_common_download_args(bhav)
    bhav.add_argument("--strict", action="store_true", help="Fail when a trading day is unavailable")
    bhav.add_argument("--include-weekends", action="store_true", help="Include Saturday and Sunday")
    bhav.set_defaults(handler=cmd_bhavcopy)

    corp = sub.add_parser("corporate-actions", help="Download corporate actions JSON by day")
    corp.add_argument("--from", dest="from_date", required=True, type=parse_date, help="Start date YYYY-MM-DD")
    corp.add_argument("--to", dest="to_date", required=True, type=parse_date, help="End date YYYY-MM-DD")
    add_common_download_args(corp)
    corp.set_defaults(handler=cmd_corporate_actions)

    idx = sub.add_parser("index-constituents", help="Download index constituent snapshots")
    idx.add_argument(
        "--date",
        dest="trade_date",
        type=parse_date,
        default=date.today(),
        help="Snapshot date label YYYY-MM-DD (default: today)",
    )
    idx.add_argument(
        "--index",
        action="append",
        dest="indices",
        help="Index name (repeatable). Default: NIFTY 50",
    )
    add_common_download_args(idx)
    idx.set_defaults(handler=cmd_index_constituents)

    status = sub.add_parser("status", help="Show staged file counts under the archive root")
    add_root_arg(status)
    status.set_defaults(handler=cmd_status)

    doctor = sub.add_parser("doctor", help="Prime an NSE session and report basic connectivity")
    doctor.set_defaults(handler=cmd_doctor)

    return parser


def cmd_bhavcopy(args: argparse.Namespace) -> int:
    root = Settings.resolve(args.root).archive_root
    downloader = BhavcopyDownloader(
        root,
        sleep_seconds=args.sleep,
        skip_existing=args.skip_existing,
        strict=args.strict,
        include_weekends=args.include_weekends,
    )
    summary = downloader.download_range(args.from_date, args.to_date)
    print(
        f"bhavcopy: downloaded={summary.downloaded_count} "
        f"skipped={summary.skipped_existing_count} failed={summary.failed_count} "
        f"root={downloader.root}"
    )
    return 0 if summary.failed_count == 0 or not args.strict else 1


def cmd_corporate_actions(args: argparse.Namespace) -> int:
    root = Settings.resolve(args.root).archive_root
    downloader = CorporateActionsDownloader(
        root,
        sleep_seconds=args.sleep,
        skip_existing=args.skip_existing,
    )
    summary = downloader.download_range(args.from_date, args.to_date)
    print(
        f"corporate-actions: downloaded={summary.downloaded_count} "
        f"skipped={summary.skipped_existing_count} root={downloader.root}"
    )
    return 0


def cmd_index_constituents(args: argparse.Namespace) -> int:
    root = Settings.resolve(args.root).archive_root
    downloader = IndexConstituentsDownloader(
        root,
        sleep_seconds=args.sleep,
        skip_existing=args.skip_existing,
    )
    indices = args.indices or list(DEFAULT_INDEX_NAMES)
    summary = downloader.download_indices(args.trade_date, indices)
    print(
        f"index-constituents: downloaded={summary.downloaded_count} "
        f"skipped={summary.skipped_existing_count} root={downloader.root}"
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    reader = ArchiveReader(args.root)
    inventory = reader.inventory()
    print(f"archive root: {reader.root}")
    for key, value in inventory.items():
        print(f"  {key}: {value}")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    client = NseHttpClient()
    try:
        client.prime()
        # Lightweight archives home probe
        payload = client.fetch_bytes("https://www.nseindia.com/", accept="text/html")
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"doctor: FAILED ({exc})", file=sys.stderr)
        return 1
    kind = "html" if payload.lstrip().startswith(b"<") else "bytes"
    print(f"doctor: OK (session primed; home returned {len(payload)} {kind})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (PowerNseError, ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
