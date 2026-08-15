"""NSE HTTP session with priming, throttle, and retries."""

import logging
import time
from collections.abc import Callable

import requests
from requests import RequestException, Response, Session
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from powernse.constants import (
    DEFAULT_USER_AGENT,
    MAX_HTTP_ATTEMPTS,
    MIN_REQUEST_INTERVAL_SECONDS,
    NSE_HOME_URL,
    RETRYABLE_STATUS_CODES,
)
from powernse.errors import DownloadError

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Referer": "https://www.nseindia.com/",
}


class RequestThrottler:
    """Enforce a true minimum interval between outbound HTTP requests."""

    def __init__(self, min_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS) -> None:
        self._min_interval_seconds = max(0.0, min_interval_seconds)
        self._last_request_monotonic: float | None = None

    def wait(self) -> None:
        if self._min_interval_seconds <= 0:
            self._last_request_monotonic = time.monotonic()
            return
        now = time.monotonic()
        if self._last_request_monotonic is not None:
            elapsed = now - self._last_request_monotonic
            remaining = self._min_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_monotonic = time.monotonic()


def looks_like_html(payload: bytes, *, content_type: str | None = None) -> bool:
    """Return True when a payload appears to be an HTML error page."""
    if content_type is not None and "text/html" in content_type.lower():
        return True
    stripped = payload[:512].lstrip()
    return stripped.startswith(b"<")


def is_retryable_nse_error(exc: BaseException) -> bool:
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        return response is not None and response.status_code in RETRYABLE_STATUS_CODES
    return isinstance(exc, RequestException)


class NseHttpClient:
    """Lifecycle owner for primed NSE sessions and throttled byte fetches."""

    def __init__(
        self,
        *,
        min_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
        session: Session | None = None,
        fetch_override: Callable[[str], bytes] | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._throttler = RequestThrottler(min_interval_seconds)
        self._fetch_override = fetch_override
        self._primed = False
        self._prime_error: str | None = None

    @property
    def primed(self) -> bool:
        return self._primed

    @property
    def prime_error(self) -> str | None:
        return self._prime_error

    def prime(self) -> None:
        """Best-effort cookie priming via the NSE home page."""
        if self._primed or self._fetch_override is not None:
            return
        try:
            self._session.get(NSE_HOME_URL, headers={**DEFAULT_HEADERS, "Accept": "*/*"}, timeout=30)
            self._primed = True
            self._prime_error = None
        except RequestException as exc:
            self._prime_error = str(exc)
            logger.warning("NSE session priming failed (continuing without cookies): %s", exc)

    def probe_home(self) -> bytes:
        """GET the NSE home page for connectivity checks (HTML allowed)."""
        self.prime()
        self._throttler.wait()
        try:
            response = self._session.get(
                NSE_HOME_URL,
                headers={**DEFAULT_HEADERS, "Accept": "text/html"},
                timeout=60,
            )
            response.raise_for_status()
        except RequestException as exc:
            raise DownloadError(self._format_http_failure(NSE_HOME_URL, exc)) from exc
        return response.content

    def fetch_bytes(self, url: str, *, accept: str = "*/*") -> bytes:
        if self._fetch_override is not None:
            self._throttler.wait()
            try:
                return self._fetch_override(url)
            except RequestException as exc:
                raise DownloadError(f"NSE fetch failed for {url}: {exc}") from exc
        self.prime()
        self._throttler.wait()
        return self._read_with_retry(url, accept=accept)

    def _read_with_retry(self, url: str, *, accept: str) -> bytes:
        @retry(
            retry=retry_if_exception(is_retryable_nse_error),
            stop=stop_after_attempt(MAX_HTTP_ATTEMPTS),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        )
        def _once() -> bytes:
            response = self._session.get(url, headers={**DEFAULT_HEADERS, "Accept": accept}, timeout=60)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type")
            payload = response.content
            if looks_like_html(payload, content_type=content_type):
                raise DownloadError(f"NSE returned HTML instead of data for {url}")
            return payload

        try:
            return _once()
        except RequestException as exc:
            raise DownloadError(self._format_http_failure(url, exc)) from exc

    @staticmethod
    def _format_http_failure(url: str, exc: RequestException) -> str:
        response: Response | None = getattr(exc, "response", None)
        if response is not None:
            return f"NSE HTTP {response.status_code} for {url}"
        return f"NSE fetch failed for {url}: {exc}"
