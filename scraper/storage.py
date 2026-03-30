from __future__ import annotations

import hashlib
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
        if self.settings.sync_mode:
            return
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

    def load_existing_documents(self) -> List[Dict[str, Any]]:
        if not self.aggregate_path.exists():
            return []
        payload = json.loads(self.aggregate_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            documents = payload.get("documents", [])
            if isinstance(documents, list):
                return [doc for doc in documents if isinstance(doc, dict)]
        return []

    def document_key(self, document: Dict[str, Any]) -> str | None:
        metadata = document.get("metadata") or {}
        key = (
            document.get("url")
            or metadata.get("canonical_url")
            or metadata.get("data_detail_uri")
            or metadata.get("source_url")
        )
        return key or None

    def partition_documents_by_key(self, documents: List[Dict[str, Any]]) -> tuple[Dict[str, Dict[str, Any]], int]:
        keyed_documents: Dict[str, Dict[str, Any]] = {}
        missing_identity_count = 0
        for document in documents:
            key = self.document_key(document)
            if not key:
                missing_identity_count += 1
                continue
            keyed_documents[key] = document
        return keyed_documents, missing_identity_count

    def document_hash(self, document: Dict[str, Any]) -> str:
        normalized = json.dumps(document, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def rewrite_documents(self, documents: List[Dict[str, Any]]) -> None:
        with self.documents_path.open("w", encoding="utf-8") as handle:
            for document in documents:
                handle.write(json.dumps(document, ensure_ascii=False) + "\n")

    def reconcile_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, int]:
        previous_documents = self.load_existing_documents()
        previous_by_key, previous_missing_identity = self.partition_documents_by_key(previous_documents)
        current_by_key, current_missing_identity = self.partition_documents_by_key(documents)

        previous_keys = set(previous_by_key)
        current_keys = set(current_by_key)
        added = current_keys - previous_keys
        deleted = previous_keys - current_keys
        shared = current_keys & previous_keys

        updated = 0
        unchanged = 0
        for key in shared:
            if self.document_hash(previous_by_key[key]) == self.document_hash(current_by_key[key]):
                unchanged += 1
            else:
                updated += 1

        return {
            "added": len(added),
            "updated": updated,
            "deleted": len(deleted),
            "unchanged": unchanged,
            "missing_identity_previous": previous_missing_identity,
            "missing_identity_current": current_missing_identity,
        }

    def export_aggregate(self, documents: List[Dict[str, Any]]) -> Dict[str, int]:
        sync_stats = {
            "added": len(documents),
            "updated": 0,
            "deleted": 0,
            "unchanged": 0,
            "missing_identity_previous": 0,
            "missing_identity_current": 0,
        }
        if self.settings.sync_mode:
            sync_stats = self.reconcile_documents(documents)
            self.rewrite_documents(documents)

        payload = {
            "_meta": {
                "profile_name": self.profile.name,
                "base_url": self.profile.base_url,
                "doc_type": self.profile.doc_type,
                "total_docs": len(documents),
                "sync_mode": self.settings.sync_mode,
                "sync_stats": sync_stats,
                "identity_resolution": {
                    "priority": [
                        "url",
                        "metadata.canonical_url",
                        "metadata.data_detail_uri",
                        "metadata.source_url"
                    ],
                    "behavior_when_missing": "Documents remain in exported output, but sync reconciliation cannot match them across runs and they are counted in missing_identity_* stats."
                },
            },
            "documents": documents,
        }
        self.aggregate_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return sync_stats
