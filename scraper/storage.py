from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set

from .config import RuntimeSettings, ScraperProfile


class StorageManager:
    def __init__(self, settings: RuntimeSettings, profile: ScraperProfile) -> None:
        self.settings = settings
        self.profile = profile
        self.output_dir = settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.documents_path = self.output_dir / f"{profile.name}.jsonl"
        self.aggregate_path = self.output_dir / f"{profile.name}.json"
        self.checkpoint_path = self.output_dir / f"{profile.name}_checkpoint.json"
        self.errors_path = self.output_dir / f"{profile.name}_errors.jsonl"

    def append_document(self, document: Dict[str, Any]) -> None:
        with self.documents_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(document, ensure_ascii=False) + "\n")

    def append_error(self, payload: Dict[str, Any]) -> None:
        if not self.settings.save_errors:
            return
        with self.errors_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def save_checkpoint(self, visited: Set[str], queued: List[Dict[str, Any]]) -> None:
        if not self.settings.save_checkpoint:
            return
        payload = {
            "visited": sorted(visited),
            "queue": queued,
        }
        self.checkpoint_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_checkpoint(self) -> Dict[str, Any]:
        if not self.settings.resume or not self.checkpoint_path.exists():
            return {"visited": [], "queue": []}
        return json.loads(self.checkpoint_path.read_text(encoding="utf-8"))

    def export_aggregate(self, documents: List[Dict[str, Any]]) -> None:
        payload = {
            "_meta": {
                "profile_name": self.profile.name,
                "base_url": self.profile.base_url,
                "doc_type": self.profile.doc_type,
                "total_docs": len(documents),
            },
            "documents": documents,
        }
        self.aggregate_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
