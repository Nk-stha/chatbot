from pathlib import Path

from scraper.config import RuntimeSettings, ScraperProfile
from scraper.storage import StorageManager


def make_profile() -> ScraperProfile:
    return ScraperProfile.model_validate(
        {
            "name": "demo",
            "base_url": "https://example.com",
            "start_urls": ["https://example.com/articles"],
            "selectors": {},
        }
    )


def test_runtime_settings_support_sync_mode(tmp_path: Path):
    settings = RuntimeSettings(output_dir=tmp_path, sync_mode=True)
    assert settings.sync_mode is True


def test_sync_export_adds_updates_and_deletes(tmp_path: Path):
    profile = make_profile()
    previous_payload = {
        "_meta": {"profile_name": profile.name, "base_url": profile.base_url, "doc_type": profile.doc_type, "total_docs": 2},
        "documents": [
            {"url": "https://example.com/items/a", "title": "Old A", "content": "same", "metadata": {"category": "x"}},
            {"url": "https://example.com/items/b", "title": "Old B", "content": "old", "metadata": {"category": "y"}},
        ],
    }
    aggregate_path = tmp_path / f"{profile.name}.json"
    aggregate_path.write_text(__import__("json").dumps(previous_payload), encoding="utf-8")

    settings = RuntimeSettings(output_dir=tmp_path, sync_mode=True)
    storage = StorageManager(settings, profile)
    documents = [
        {"url": "https://example.com/items/a", "title": "Old A", "content": "same", "metadata": {"category": "x"}},
        {"url": "https://example.com/items/b", "title": "New B", "content": "new", "metadata": {"category": "y"}},
        {"url": "https://example.com/items/c", "title": "New C", "content": "fresh", "metadata": {"category": "z"}},
    ]

    stats = storage.export_aggregate(documents)

    assert stats == {"added": 1, "updated": 1, "deleted": 0, "unchanged": 1}
    payload = __import__("json").loads(aggregate_path.read_text(encoding="utf-8"))
    assert payload["_meta"]["sync_mode"] is True
    assert payload["_meta"]["sync_stats"] == stats
    assert [doc["url"] for doc in payload["documents"]] == [
        "https://example.com/items/a",
        "https://example.com/items/b",
        "https://example.com/items/c",
    ]
    jsonl_lines = (tmp_path / f"{profile.name}.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(jsonl_lines) == 3


def test_sync_export_removes_deleted_records(tmp_path: Path):
    profile = make_profile()
    previous_payload = {
        "_meta": {"profile_name": profile.name, "base_url": profile.base_url, "doc_type": profile.doc_type, "total_docs": 2},
        "documents": [
            {"url": "https://example.com/items/a", "title": "A", "content": "same", "metadata": {}},
            {"url": "https://example.com/items/b", "title": "B", "content": "gone", "metadata": {}},
        ],
    }
    aggregate_path = tmp_path / f"{profile.name}.json"
    aggregate_path.write_text(__import__("json").dumps(previous_payload), encoding="utf-8")

    settings = RuntimeSettings(output_dir=tmp_path, sync_mode=True)
    storage = StorageManager(settings, profile)
    stats = storage.export_aggregate([
        {"url": "https://example.com/items/a", "title": "A", "content": "same", "metadata": {}},
    ])

    assert stats == {"added": 0, "updated": 0, "deleted": 1, "unchanged": 1}
    payload = __import__("json").loads(aggregate_path.read_text(encoding="utf-8"))
    assert [doc["url"] for doc in payload["documents"]] == ["https://example.com/items/a"]
