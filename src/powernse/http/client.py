"""NSE HTTP session with priming, throttle, and retries."""

from __future__ import annotations

import logging
from collections.abc import Callable

import requests
from pyrate_limiter import Duration, Limiter, Rate
from requests import RequestException, Session
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from powernse.constants import (
    DEFAULT_USER_AGENT,
    MAX_HTTP_ATTEMPTS,
    MIN_REQUEST_INTERVAL_SECONDS,
    NSE_HOME_URL,
    RETRYABLE_STATUS_CODES,
)

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Referer": "https://www.nseindia.com/",
}


class RequestThrottler:
    """Enforce a minimum interval between outbound HTTP requests."""

    def __init__(self, min_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS) -> None:
        requests_per_second = max(1, round(1.0 / min_interval_seconds))
        self._limiter = Limiter(Rate(requests_per_second, Duration.SECOND))

    def wait(self) -> None:
        self._limiter.try_acquire("nse")


def looks_like_html(payload: bytes) -> bool:
    """Return True when a payload appears to be an HTML error page."""
    stripped = payload[:512].lstrip()
    return stripped.startswith(b"<") or b"text/html" in stripped.lower()


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

    def prime(self) -> None:
        """Best-effort cookie priming via the NSE home page."""
        if self._primed or self._fetch_override is not None:
            return
        try:
            self._session.get(NSE_HOME_URL, headers={**DEFAULT_HEADERS, "Accept": "*/*"}, timeout=30)
            self._primed = True
        except RequestException as exc:
            logger.warning("NSE session priming failed (continuing without cookies): %s", exc)

    def fetch_bytes(self, url: str, *, accept: str = "*/*") -> bytes:
        if self._fetch_override is not None:
            self._throttler.wait()
            return self._fetch_override(url)
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
            return response.content

        return _once()
