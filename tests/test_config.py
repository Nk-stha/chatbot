from scraper.config import RuntimeSettings, ScraperProfile


def test_profile_defaults_allowed_domain():
    profile = ScraperProfile.model_validate(
        {
            "name": "demo",
            "base_url": "https://example.com",
            "start_urls": ["https://example.com/articles"],
            "selectors": {},
        }
    )
    assert profile.allowed_domains == ["example.com"]


def test_selector_list_normalizes_single_value():
    profile = ScraperProfile.model_validate(
        {
            "name": "demo",
            "base_url": "https://example.com",
            "start_urls": ["https://example.com/articles"],
            "selectors": {"title": "h1"},
        }
    )
    assert profile.selector_list("title") == ["h1"]


def test_runtime_settings_support_sync_mode(tmp_path):
    settings = RuntimeSettings(output_dir=tmp_path, sync_mode=True)
    assert settings.sync_mode is True
