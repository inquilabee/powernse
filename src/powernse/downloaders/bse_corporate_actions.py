"""Download BSE's corporate-actions feed -- a dividend-amount cross-check for the NSE source."""

import json
import logging
from collections import defaultdict
from datetime import date
from typing import ClassVar
from urllib.parse import urlencode

from powernse.calendar import iter_trading_dates
from powernse.constants import BSE_CORPORATE_ACTIONS_API_URL, BSE_HOME_URL
from powernse.datasets import BSE_CORPORATE_ACTIONS
from powernse.downloaders.base import ArchiveDownloader
from powernse.errors import DownloadError, PayloadError
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)

Row = dict[str, object]


class BseCorporateActionsDownloader(ArchiveDownloader):
    """Fetch BSE equity corporate actions by calendar year, stage one JSON file per ex-date."""

    accept: ClassVar[str] = "application/json"
    request_headers: ClassVar[dict[str, str]] = {"Referer": BSE_HOME_URL}

    @staticmethod
    def exdate(row: Row) -> date | None:
        """Ex-date from a BSE feed row's ``exdate`` (``YYYYMMDD``), or ``None``."""
        token = str(row.get("exdate") or "").strip()
        if len(token) != 8 or not token.isdigit():
            return None
        try:
            return date(int(token[:4]), int(token[4:6]), int(token[6:8]))
        except ValueError:
            return None

    @staticmethod
    def request_url(from_date: date, to_date: date) -> str:
        params = {
            "Fdate": from_date.strftime("%Y%m%d"),
            "TDate": to_date.strftime("%Y%m%d"),
            "ddlcategorys": "E",
            "ddlindex": "",
            "scripcode": "",
            "segment": "Equity",
            "strSearch": "",
        }
        return f"{BSE_CORPORATE_ACTIONS_API_URL}?{urlencode(params)}"

    def download_range(self, from_date: date, to_date: date) -> DownloadSummary:
        if from_date > to_date:
            msg = f"from_date {from_date} must be on or before to_date {to_date}"
            raise ValueError(msg)

        downloaded = skipped = failed = 0
        for year in range(from_date.year, to_date.year + 1):
            span_start = max(from_date, date(year, 1, 1))
            span_end = min(to_date, date(year, 12, 31))
            days = list(iter_trading_dates(span_start, span_end, all_calendar_days=True))
            if all(self.archive.has_staged(BSE_CORPORATE_ACTIONS, day) for day in days):
                skipped += len(days)
                continue
            try:
                downloaded += self._download_year(span_start, span_end)
            except (DownloadError, PayloadError) as exc:
                if self._strict:
                    raise
                logger.warning("Skipping BSE corporate actions %s-%s: %s", span_start, span_end, exc)
                failed += 1
        return DownloadSummary(downloaded_count=downloaded, skipped_existing_count=skipped, failed_count=failed)

    def _download_year(self, span_start: date, span_end: date) -> int:
        url = self.request_url(span_start, span_end)
        rows = self._decode_rows(self.fetch_bytes_throttled(url), url)
        by_day: dict[date, list[Row]] = defaultdict(list)
        for row in rows:
            day = self.exdate(row)
            if day is not None and span_start <= day <= span_end:
                by_day[day].append(row)

        written = 0
        for day, day_rows in by_day.items():
            relative = self.archive.staged_key(BSE_CORPORATE_ACTIONS, day)
            if self.skip_existing and self.destination_exists(relative):
                continue
            self.persist_bytes(
                url,
                relative,
                json.dumps(day_rows).encode("utf-8"),
                unavailable_message=f"BSE corporate actions unavailable for {day.isoformat()}: {url}",
            )
            written += 1
        return written

    @staticmethod
    def _decode_rows(payload: bytes, url: str) -> list[Row]:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            msg = f"BSE corporate actions payload is not valid JSON: {url}"
            raise PayloadError(msg) from exc
        if not isinstance(decoded, list):
            msg = f"BSE corporate actions payload must be a JSON list: {url}"
            raise PayloadError(msg)
        return [item for item in decoded if isinstance(item, dict)]
