from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from loguru import logger

from .config import RuntimeSettings, ScraperProfile
from .crawler import Crawler


def load_profile(path: str | Path) -> ScraperProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ScraperProfile.model_validate(payload)


def build_runtime_settings(args: argparse.Namespace) -> RuntimeSettings:
    return RuntimeSettings(
        output_dir=args.output_dir,
        output_format=args.output_format,
        resume=not args.no_resume,
        sync_mode=args.sync,
        timeout_seconds=args.timeout,
    )



def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Production-oriented web scraper")
    parser.add_argument("--profile", required=True, help="Path to a JSON scraper profile")
    parser.add_argument("--output-dir", default="output", help="Directory for crawl results")
    parser.add_argument("--output-format", choices=["json", "jsonl"], default="jsonl")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--sync", action="store_true", help="Reconcile output by adding new records, updating changed ones, and removing missing ones")
    return parser.parse_args(argv)



def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    profile = load_profile(args.profile)
    settings = build_runtime_settings(args)
    logger.info(f"Running scraper profile: {profile.name}")
    crawler = Crawler(profile, settings)
    crawler.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
