from __future__ import annotations

import re
from collections import deque
from typing import Any, Deque, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse

from loguru import logger

from .browser_client import BrowserClient
from .config import RuntimeSettings, ScraperProfile
from .extractors import Extractor
from .http_client import HttpClient
from .storage import StorageManager


class Crawler:
    def __init__(self, profile: ScraperProfile, settings: Optional[RuntimeSettings] = None) -> None:
        self.profile = profile
        self.settings = settings or RuntimeSettings()
        self.http_client = HttpClient(self.settings, profile.request_delay_seconds)
        self.browser_client = BrowserClient() if profile.render_mode in {"browser", "auto"} else None
        self.extractor = Extractor(profile)
        self.storage = StorageManager(self.settings, profile)
        self.documents: List[Dict[str, Any]] = []
        self.stats = {"pages_visited": 0, "docs_scraped": 0, "errors": 0}

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        query_pairs = sorted(parse_qsl(parsed.query, keep_blank_values=True))
        query = urlencode(query_pairs)
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if query:
            normalized = f"{normalized}?{query}"
        return normalized

    def is_allowed_url(self, url: str) -> bool:
        normalized = self.normalize_url(url)
        host = urlparse(normalized).netloc
        if self.profile.allowed_domains and host not in self.profile.allowed_domains:
            return False
        if self.profile.include_patterns and not any(re.search(pattern, normalized) for pattern in self.profile.include_patterns):
            return False
        if self.profile.exclude_patterns and any(re.search(pattern, normalized) for pattern in self.profile.exclude_patterns):
            return False
        return True

    def looks_like_detail(self, url: str) -> bool:
        if self.profile.is_pdf or url.lower().endswith(".pdf"):
            return True
        keywords = self.profile.detail_url_keywords
        if not keywords:
            return True
        return any(keyword in url for keyword in keywords)

    def fetch_html(self, url: str) -> str:
        use_browser = self.profile.render_mode == "browser"
        if self.profile.render_mode == "auto" and self.browser_client and self.browser_client.available:
            use_browser = False

        if use_browser and self.browser_client:
            return self.browser_client.fetch_html(
                url,
                wait_until=self.profile.browser_wait_until,
                wait_for_selector=self.profile.browser_wait_for,
                timeout_ms=self.settings.timeout_seconds * 1000,
            )

        result = self.http_client.fetch(url)
        html = result.html or ""
        if self.profile.render_mode == "auto" and self.browser_client and self.browser_client.available:
            if "__NEXT_DATA__" in html or "window.__NUXT__" in html or len(html.strip()) < 500:
                try:
                    return self.browser_client.fetch_html(
                        url,
                        wait_until=self.profile.browser_wait_until,
                        wait_for_selector=self.profile.browser_wait_for,
                        timeout_ms=self.settings.timeout_seconds * 1000,
                    )
                except Exception:
                    return html
        return html

    def load_queue(self) -> tuple[Deque[Dict[str, Any]], set[str]]:
        checkpoint = self.storage.load_checkpoint()
        visited = {self.normalize_url(url) for url in checkpoint.get("visited", [])}
        queue: Deque[Dict[str, Any]] = deque(checkpoint.get("queue", []))
        if not queue:
            queue = deque({"url": url, "depth": 0} for url in self.profile.start_urls)
        return queue, visited

    def run(self) -> List[Dict[str, Any]]:
        logger.info(f"Starting profile: {self.profile.name}")
        queue, visited = self.load_queue()

        while queue and (
            self.profile.max_pages is None or self.stats["pages_visited"] < self.profile.max_pages
        ):
            item = queue.popleft()
            current_url = self.normalize_url(item["url"])
            depth = item.get("depth", 0)

            if current_url in visited or not self.is_allowed_url(current_url):
                continue

            visited.add(current_url)
            self.stats["pages_visited"] += 1

            try:
                if self.looks_like_detail(current_url):
                    if self.profile.is_pdf or current_url.lower().endswith(".pdf"):
                        document = {
                            "url": current_url,
                            "title": current_url.rstrip("/").split("/")[-1].replace(".pdf", ""),
                            "content": "",
                            "metadata": {"source_url": current_url, "doc_type": self.profile.doc_type, "file_type": "pdf"},
                            "file_type": "pdf",
                            "download_url": current_url,
                        }
                    else:
                        html = self.fetch_html(current_url)
                        document = self.extractor.build_document(current_url, html)
                    self.documents.append(document)
                    self.storage.append_document(document)
                    self.stats["docs_scraped"] += 1
                    continue

                html = self.fetch_html(current_url)
                soup = self.extractor.make_soup(html)
                detail_urls = self.extractor.extract_links(soup)
                pagination_urls = self.extractor.extract_pagination(soup, current_url)

                next_depth = depth + 1
                if next_depth <= self.profile.max_depth:
                    for next_url in detail_urls + pagination_urls:
                        normalized = self.normalize_url(next_url)
                        if normalized not in visited and self.is_allowed_url(normalized):
                            queue.append({"url": normalized, "depth": next_depth})

            except Exception as exc:
                self.stats["errors"] += 1
                logger.error(f"Error processing {current_url}: {exc}")
                self.storage.append_error({"url": current_url, "error": str(exc)})
            finally:
                self.storage.save_checkpoint(visited, list(queue))

        sync_stats = self.storage.export_aggregate(self.documents)
        if self.settings.sync_mode:
            added = sync_stats.get("added", 0) if isinstance(sync_stats, dict) else 0
            updated = sync_stats.get("updated", 0) if isinstance(sync_stats, dict) else 0
            deleted = sync_stats.get("deleted", 0) if isinstance(sync_stats, dict) else 0
            unchanged = sync_stats.get("unchanged", 0) if isinstance(sync_stats, dict) else 0
            missing_identity_current = sync_stats.get("missing_identity_current", 0) if isinstance(sync_stats, dict) else 0
            logger.success(
                f"Completed profile '{self.profile.name}' | Visited={self.stats['pages_visited']} "
                f"Scraped={self.stats['docs_scraped']} Errors={self.stats['errors']} "
                f"Added={added} Updated={updated} Deleted={deleted} Unchanged={unchanged} "
                f"MissingIdentityCurrent={missing_identity_current}"
            )
        else:
            logger.success(
                f"Completed profile '{self.profile.name}' | Visited={self.stats['pages_visited']} "
                f"Scraped={self.stats['docs_scraped']} Errors={self.stats['errors']}"
            )
        if self.browser_client:
            self.browser_client.close()
        return self.documents
