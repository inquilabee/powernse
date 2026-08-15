"""Download NSE corporate action reports into the archive staging tree."""

import json
import logging
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

from powernse.archive import RAW_CORPORATE_ACTIONS_DIR, archive_key
from powernse.calendar import iter_trading_dates
from powernse.constants import CORPORATE_ACTIONS_API_URL, DEFAULT_SLEEP_SECONDS
from powernse.downloaders.base import ArchiveDownloader
from powernse.errors import DownloadError, PayloadError
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)

CA_DATE_KEYS = ("exDate", "exdate", "recDate", "recordDate", "anouncementDate", "date")
CA_BATCH_DAYS = 7


def corporate_actions_staged_path(root: Path, trade_date: date) -> Path:
    """Path for a daily corporate actions JSON file under the archive root."""
    return root / RAW_CORPORATE_ACTIONS_DIR / str(trade_date.year) / f"{trade_date.isoformat()}.json"


def corporate_actions_staged_key(trade_date: date) -> str:
    return archive_key(
        RAW_CORPORATE_ACTIONS_DIR.as_posix(),
        str(trade_date.year),
        f"{trade_date.isoformat()}.json",
    )


def corporate_actions_request_url(from_date: date, to_date: date) -> str:
    """Build the NSE corporate actions API URL for a date span."""
    params = {
        "index": "equities",
        "from_date": from_date.strftime("%d-%m-%Y"),
        "to_date": to_date.strftime("%d-%m-%Y"),
    }
    return f"{CORPORATE_ACTIONS_API_URL}?{urlencode(params)}"


def parse_corporate_action_date(record: dict[str, object]) -> date | None:
    for key in CA_DATE_KEYS:
        raw = record.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
        for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%d-%b-%y", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
    return None


class CorporateActionsDownloader(ArchiveDownloader):
    """Fetch corporate action JSON archives into the archive root."""

    def __init__(
        self,
        root: Path | str,
        *,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
        skip_existing: bool = True,
        strict: bool = False,
        all_calendar_days: bool = False,
        fetch_bytes: Callable[[str], bytes] | None = None,
    ) -> None:
        super().__init__(
            root,
            sleep_seconds=sleep_seconds,
            skip_existing=skip_existing,
            fetch_bytes=fetch_bytes,
            default_accept="application/json",
        )
        self._strict = strict
        self._all_calendar_days = all_calendar_days

    def download_range(self, from_date: date, to_date: date) -> DownloadSummary:
        if from_date > to_date:
            msg = f"from_date {from_date} must be on or before to_date {to_date}"
            raise ValueError(msg)

        downloaded = 0
        skipped = 0
        failed = 0
        missing: list[date] = []
        for trade_date in iter_trading_dates(from_date, to_date, all_calendar_days=self._all_calendar_days):
            relative = corporate_actions_staged_key(trade_date)
            if self.skip_existing and self.destination_exists(relative):
                skipped += 1
            else:
                missing.append(trade_date)

        for index in range(0, len(missing), CA_BATCH_DAYS):
            batch_days = missing[index : index + CA_BATCH_DAYS]
            span_start = batch_days[0]
            span_end = batch_days[-1]
            try:
                downloaded += self._download_batch(batch_days, span_start, span_end)
            except (DownloadError, PayloadError) as exc:
                if self._strict:
                    raise
                logger.warning("Skipping corporate actions %s–%s: %s", span_start, span_end, exc)
                failed += len(batch_days)

        return DownloadSummary(
            downloaded_count=downloaded,
            skipped_existing_count=skipped,
            failed_count=failed,
        )

    def _download_batch(self, batch_days: list[date], span_start: date, span_end: date) -> int:
        url = corporate_actions_request_url(span_start, span_end)
        payload = self.fetch_bytes_throttled(url)
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            msg = f"Corporate actions payload is not valid JSON: {url}"
            raise PayloadError(msg) from exc
        if not isinstance(decoded, list):
            msg = f"Corporate actions payload must be a JSON list: {url}"
            raise PayloadError(msg)
        by_day: dict[date, list[dict[str, object]]] = {day: [] for day in batch_days}
        undated_count = 0
        for item in decoded:
            if not isinstance(item, dict):
                continue
            item_date = parse_corporate_action_date(item)
            if item_date is None:
                undated_count += 1
                logger.warning("Skipping undated corporate-action record in batch %s–%s", span_start, span_end)
            elif item_date in by_day:
                by_day[item_date].append(item)
        if undated_count:
            logger.warning(
                "Dropped %s undated corporate-action record(s) for %s–%s",
                undated_count,
                span_start,
                span_end,
            )
        written = 0
        for day in batch_days:
            relative = corporate_actions_staged_key(day)
            day_payload = json.dumps(by_day[day]).encode("utf-8")
            self.persist_bytes(
                url,
                relative,
                day_payload,
                unavailable_message=f"Corporate actions unavailable for {day.isoformat()}: {url}",
            )
            written += 1
        return written
