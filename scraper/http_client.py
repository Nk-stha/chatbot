from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import RuntimeSettings


@dataclass
class FetchResult:
    url: str
    html: Optional[str]
    status_code: Optional[int]
    final_url: str
    content_type: str


class DomainRateLimiter:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = max(0.0, delay_seconds)
        self._lock = threading.Lock()
        self._last_seen: dict[str, float] = {}

    def wait(self, url: str) -> None:
        host = urlparse(url).netloc
        if not host or self.delay_seconds <= 0:
            return

        with self._lock:
            now = time.monotonic()
            last_seen = self._last_seen.get(host, 0.0)
            remaining = self.delay_seconds - (now - last_seen)
            if remaining > 0:
                time.sleep(remaining)
                now = time.monotonic()
            self._last_seen[host] = now


class HttpClient:
    def __init__(self, settings: RuntimeSettings, delay_seconds: float) -> None:
        self.settings = settings
        self.rate_limiter = DomainRateLimiter(delay_seconds)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(requests.RequestException),
        reraise=True,
    )
    def fetch(self, url: str) -> FetchResult:
        self.rate_limiter.wait(url)
        response = self.session.get(url, timeout=self.settings.timeout_seconds)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return FetchResult(
            url=url,
            html=response.text,
            status_code=response.status_code,
            final_url=response.url,
            content_type=response.headers.get("Content-Type", ""),
        )
