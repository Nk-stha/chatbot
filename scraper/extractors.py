from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .config import ScraperProfile

TAILWIND_HIDDEN_CLASSES = {
    "hidden",
    "invisible",
    "opacity-0",
    "pointer-events-none",
    "sr-only",
    "screen-reader-only",
}


class Extractor:
    def __init__(self, profile: ScraperProfile) -> None:
        self.profile = profile

    def is_element_hidden(self, elem: Any) -> bool:
        if not self.profile.tailwind_optimized:
            return False
        class_attr = elem.get("class", [])
        if isinstance(class_attr, str):
            class_attr = class_attr.split()
        return any(hidden_class in class_attr for hidden_class in TAILWIND_HIDDEN_CLASSES)

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()

    def make_soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def selector_allows_hidden(self, selector: str) -> bool:
        return "meta-" in selector or "sr-only" in selector

    def text_from_element(self, elem: Any) -> str:
        text = elem.get("data-value") or elem.get_text(separator=" ", strip=True)
        if text:
            return self.clean_text(text)

        data_attributes = {
            key[5:].replace("-", "_"): value
            for key, value in elem.attrs.items()
            if key.startswith("data-") and key not in {"data-role", "data-detail-uri", "data-value"}
        }
        if data_attributes:
            return self.clean_text("; ".join(f"{key}={value}" for key, value in data_attributes.items()))
        return ""

    def first_text_match(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
        for selector in selectors:
            allow_hidden = self.selector_allows_hidden(selector)
            for elem in soup.select(selector):
                if self.is_element_hidden(elem) and not allow_hidden:
                    continue
                text = self.text_from_element(elem)
                if text:
                    return text
        return None

    def first_element(self, soup: BeautifulSoup, selectors: List[str]):
        for selector in selectors:
            allow_hidden = self.selector_allows_hidden(selector)
            elem = soup.select_one(selector)
            if elem and (allow_hidden or not self.is_element_hidden(elem)):
                return elem
        return None

    def extract_url_from_element(self, elem: Any) -> Optional[str]:
        candidate = elem.get("data-detail-uri") or elem.get("href") or elem.get("data-href")
        if candidate:
            return urljoin(self.profile.base_url, candidate)

        descendant = elem.select_one("[data-detail-uri], a[href], [data-href]")
        if descendant is None:
            return None

        nested_candidate = descendant.get("data-detail-uri") or descendant.get("href") or descendant.get("data-href")
        if not nested_candidate:
            return None
        return urljoin(self.profile.base_url, nested_candidate)

    def extract_links(self, soup: BeautifulSoup) -> List[str]:
        urls: List[str] = []
        selectors = self.profile.selector_list("list_links")
        for selector in selectors:
            for tag in soup.select(selector):
                allow_hidden = self.selector_allows_hidden(selector)
                if self.is_element_hidden(tag) and not allow_hidden:
                    continue
                full_url = self.extract_url_from_element(tag)
                if full_url and full_url not in urls:
                    urls.append(full_url)
        return urls

    def extract_pagination(self, soup: BeautifulSoup, current_url: str) -> List[str]:
        urls: List[str] = []
        for selector in self.profile.pagination_selectors():
            allow_hidden = self.selector_allows_hidden(selector)
            for elem in soup.select(selector):
                if self.is_element_hidden(elem) and not allow_hidden:
                    continue
                full_url = self.extract_url_from_element(elem)
                if full_url and full_url != current_url and full_url not in urls:
                    urls.append(full_url)
        return urls

    def extract_title(self, soup: BeautifulSoup, url: str) -> str:
        title = self.first_text_match(soup, self.profile.selector_list("title"))
        if title:
            return title
        title_tag = soup.find("title")
        if title_tag:
            return self.clean_text(title_tag.get_text(strip=True))
        return url.rstrip("/").split("/")[-1] or "Untitled"

    def extract_content(self, soup: BeautifulSoup) -> str:
        selectors = self.profile.selector_list("content")
        if not selectors:
            selectors = ["main", "article", "[role='main']", ".content", "body"]

        elem = self.first_element(soup, selectors)
        if elem is None:
            return ""

        for unwanted in elem(["script", "style", "nav", "footer", "noscript"]):
            unwanted.decompose()
        return self.clean_text(elem.get_text(separator=" ", strip=True))

    def extract_metadata(self, soup: BeautifulSoup, url: str, title: str) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "source_url": url,
            "doc_type": self.profile.doc_type,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "page_title": title,
        }
        for field in self.profile.metadata_fields:
            value = self.first_text_match(soup, self.profile.selector_list(field))
            meta[field] = value or ""
        return meta

    def build_document(self, url: str, html: str) -> Dict[str, Any]:
        soup = self.make_soup(html)
        title = self.extract_title(soup, url)
        content = self.extract_content(soup)
        metadata = self.extract_metadata(soup, url, title)
        return {
            "url": url,
            "title": title,
            "content": content,
            "metadata": metadata,
            "file_type": "html",
            "content_length": len(content),
            "word_count": len(content.split()) if content else 0,
        }
