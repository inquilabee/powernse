"""Download NSE corporate action reports into the archive staging tree."""

import json
import logging
from datetime import date
from typing import ClassVar
from urllib.parse import urlencode

from powernse.calendar import iter_trading_dates
from powernse.constants import CORPORATE_ACTIONS_API_URL
from powernse.corporate_actions import ex_date_of
from powernse.datasets import CORPORATE_ACTIONS
from powernse.downloaders.base import ArchiveDownloader
from powernse.errors import DownloadError, PayloadError
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)

CA_BATCH_DAYS = 7


class CorporateActionsDownloader(ArchiveDownloader):
    """Fetch corporate action JSON archives into the archive root."""

    accept: ClassVar[str] = "application/json"

    @staticmethod
    def request_url(from_date: date, to_date: date) -> str:
        """NSE corporate-actions API URL for a date span."""
        params = {
            "index": "equities",
            "from_date": from_date.strftime("%d-%m-%Y"),
            "to_date": to_date.strftime("%d-%m-%Y"),
        }
        return f"{CORPORATE_ACTIONS_API_URL}?{urlencode(params)}"

    def download_range(self, from_date: date, to_date: date) -> DownloadSummary:
        if from_date > to_date:
            msg = f"from_date {from_date} must be on or before to_date {to_date}"
            raise ValueError(msg)

        downloaded = 0
        skipped = 0
        failed = 0
        missing: list[date] = []
        for trade_date in iter_trading_dates(from_date, to_date, all_calendar_days=self._all_calendar_days):
            relative = self.archive.staged_key(CORPORATE_ACTIONS, trade_date)
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
        url = self.request_url(span_start, span_end)
        records = self._decode_records(self.fetch_bytes_throttled(url), url)
        by_day = self._bucket_by_day(records, batch_days, span_start, span_end)
        for day in batch_days:
            self.persist_bytes(
                url,
                self.archive.staged_key(CORPORATE_ACTIONS, day),
                json.dumps(by_day[day]).encode("utf-8"),
                unavailable_message=f"Corporate actions unavailable for {day.isoformat()}: {url}",
            )
        return len(batch_days)

    @staticmethod
    def _decode_records(payload: bytes, url: str) -> list[dict[str, object]]:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            msg = f"Corporate actions payload is not valid JSON: {url}"
            raise PayloadError(msg) from exc
        if not isinstance(decoded, list):
            msg = f"Corporate actions payload must be a JSON list: {url}"
            raise PayloadError(msg)
        return [item for item in decoded if isinstance(item, dict)]

    @staticmethod
    def _bucket_by_day(
        records: list[dict[str, object]], batch_days: list[date], span_start: date, span_end: date
    ) -> dict[date, list[dict[str, object]]]:
        by_day: dict[date, list[dict[str, object]]] = {day: [] for day in batch_days}
        undated = 0
        for item in records:
            item_date = ex_date_of(item)
            if item_date is None:
                undated += 1
            elif item_date in by_day:
                by_day[item_date].append(item)
        if undated:
            logger.warning("Dropped %s undated corporate-action record(s) for %s-%s", undated, span_start, span_end)
        return by_day
