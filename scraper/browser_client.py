from __future__ import annotations

from typing import Optional


class BrowserClient:
    def __init__(self) -> None:
        self.available = False
        self._playwright = None
        self._browser = None
        try:
            from playwright.sync_api import sync_playwright  # type: ignore

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self.available = True
        except Exception:
            self.available = False
            self._playwright = None
            self._browser = None

    def fetch_html(
        self,
        url: str,
        wait_until: str = "networkidle",
        wait_for_selector: Optional[str] = None,
        timeout_ms: int = 20000,
    ) -> str:
        if not self.available or self._browser is None:
            raise RuntimeError("Playwright is not available. Install playwright and browsers first.")

        page = self._browser.new_page()
        try:
            page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            if wait_for_selector:
                page.wait_for_selector(wait_for_selector, timeout=timeout_ms)
            return page.content()
        finally:
            page.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
