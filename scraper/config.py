from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScraperProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    base_url: str
    start_urls: List[str]
    selectors: Dict[str, Any] = Field(default_factory=dict)
    metadata_fields: List[str] = Field(default_factory=list)
    doc_type: str = "page"
    pagination_selector: Optional[Any] = None
    allowed_domains: List[str] = Field(default_factory=list)
    detail_url_keywords: List[str] = Field(default_factory=list)
    include_patterns: List[str] = Field(default_factory=list)
    exclude_patterns: List[str] = Field(default_factory=list)
    render_mode: Literal["http", "browser", "auto"] = "auto"
    is_pdf: bool = False
    tailwind_optimized: bool = True
    max_pages: Optional[int] = None
    max_depth: int = 2
    request_delay_seconds: float = 0.3
    browser_wait_for: Optional[str] = None
    browser_wait_until: Literal["load", "domcontentloaded", "networkidle"] = "networkidle"
    @field_validator("max_pages")
    @classmethod
    def validate_max_pages(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        return max(1, value)


    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("base_url must be an absolute URL")
        return value.rstrip("/") + "/"

    @field_validator("start_urls")
    @classmethod
    def validate_start_urls(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("start_urls cannot be empty")
        return value

    @model_validator(mode="after")
    def populate_allowed_domains(self) -> "ScraperProfile":
        if not self.allowed_domains:
            host = urlparse(self.base_url).netloc
            if host:
                self.allowed_domains = [host]
        return self

    def selector_list(self, key: str) -> List[str]:
        value = self.selectors.get(key)
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [item for item in value if item]
        return [value]

    def pagination_selectors(self) -> List[str]:
        value = self.pagination_selector
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [item for item in value if item]
        return [value]


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    output_dir: Path = Path("output")
    output_format: Literal["json", "jsonl"] = "jsonl"
    save_errors: bool = True
    save_checkpoint: bool = True
    resume: bool = True
    sync_mode: bool = False
    concurrency: int = 5
    timeout_seconds: int = 20
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    )

    @field_validator("concurrency")
    @classmethod
    def validate_concurrency(cls, value: int) -> int:
        return max(1, min(value, 32))

    @field_validator("output_dir", mode="before")
    @classmethod
    def coerce_output_dir(cls, value: Any) -> Path:
        return Path(value)
