from scraper.config import ScraperProfile
from scraper.extractors import Extractor


HTML = """
<html>
  <head><title>Fixture Title</title></head>
  <body>
    <main>
      <article>
        <h1>Visible Heading</h1>
        <div class="author">Jane Doe</div>
        <p>Hello world from fixture.</p>
      </article>
    </main>
  </body>
</html>
"""


def build_profile() -> ScraperProfile:
    return ScraperProfile.model_validate(
        {
            "name": "fixture",
            "base_url": "https://example.com",
            "start_urls": ["https://example.com/articles"],
            "selectors": {
                "title": ["h1", "title"],
                "content": ["main article"],
                "author": [".author"],
            },
            "metadata_fields": ["author"],
        }
    )


def test_extract_document():
    extractor = Extractor(build_profile())
    document = extractor.build_document("https://example.com/articles/1", HTML)
    assert document["title"] == "Visible Heading"
    assert "Hello world from fixture." in document["content"]
    assert document["metadata"]["author"] == "Jane Doe"
