# Current Scraper Implementation

## Overview

This project is now a **profile-driven modular web scraping framework**.

It is built to crawl scraper-friendly SSR pages that expose structured attributes such as:

- `data-role`
- `data-detail-uri`
- hidden `meta-*` blocks
- query-parameter pagination like `?page=1`

The current implementation is optimized for the EntranceGateway site and includes dedicated profiles for:

- syllabus
- old questions
- notes
- colleges
- courses
- blogs
- trainings
- quiz

The scraper can now:

- crawl list pages
- discover detail pages automatically
- follow pagination
- extract structured content and metadata
- save JSON and JSONL outputs
- save checkpoints and error logs
- resume interrupted runs
- run in unlimited crawl mode
- run in sync mode to reconcile add/update/delete changes

---

## Entry Point

### [web_scraper.py](web_scraper.py)

This file is a thin compatibility entrypoint.

Current responsibility:
- import `main` from `scraper.cli`
- execute the CLI entrypoint

This means the real application logic now lives inside the `scraper/` package.

---

## Package Structure

### [scraper/__init__.py](scraper/__init__.py)
Package marker and convenience import surface.

### [scraper/cli.py](scraper/cli.py)
Handles command-line execution.

### [scraper/config.py](scraper/config.py)
Defines validated runtime and profile models using Pydantic.

### [scraper/http_client.py](scraper/http_client.py)
Performs HTTP fetches with retry and timeout behavior.

### [scraper/browser_client.py](scraper/browser_client.py)
Optional browser-rendered fetch support for JS-heavy pages.

### [scraper/extractors.py](scraper/extractors.py)
Parses HTML and extracts links, content, and metadata.

### [scraper/crawler.py](scraper/crawler.py)
Coordinates queue-based crawling and traversal.

### [scraper/storage.py](scraper/storage.py)
Handles output files, checkpoints, errors, aggregate export, and sync reconciliation.

---

## Configuration Model

### ScraperProfile
Defined in [config.py](scraper/config.py)

This model defines site/profile behavior.

Key fields:

- `name`: profile name used for output file naming
- `base_url`: base absolute URL for the target site
- `start_urls`: initial list pages to crawl
- `selectors`: field extraction and list link selectors
- `metadata_fields`: logical metadata fields to include in output
- `doc_type`: document type label such as `syllabus`, `question`, `blog`
- `pagination_selector`: selectors used to discover next pages
- `allowed_domains`: domain allowlist
- `detail_url_keywords`: keywords used to decide whether a URL is a detail page
- `include_patterns`: regex allow patterns
- `exclude_patterns`: regex deny patterns
- `render_mode`: `http`, `browser`, or `auto`
- `is_pdf`: marks a profile as PDF-oriented
- `tailwind_optimized`: compatibility flag retained from earlier iterations
- `max_pages`: now supports `null` for unlimited crawling
- `max_depth`: queue traversal depth limit
- `request_delay_seconds`: request throttling delay
- `browser_wait_for`: optional selector for browser rendering waits
- `browser_wait_until`: browser wait strategy

Validation behavior:

- `base_url` must be a valid absolute URL
- `start_urls` cannot be empty
- `allowed_domains` is auto-populated from `base_url` if omitted
- selector and pagination helpers normalize single values to lists
- `max_pages: null` is accepted and means unlimited crawling

### RuntimeSettings
Also defined in [config.py](scraper/config.py)

Key runtime fields:

- `output_dir`
- `output_format`
- `save_errors`
- `save_checkpoint`
- `resume`
- `sync_mode`
- `concurrency`
- `timeout_seconds`
- `user_agent`

Important addition:

- `sync_mode: bool = False`

When enabled, final output is reconciled against previously saved aggregate data.

---

## CLI Behavior

### [cli.py](scraper/cli.py)

The CLI currently supports:

- `--profile`
- `--output-dir`
- `--output-format`
- `--timeout`
- `--no-resume`
- `--sync`

### Current behavior

`load_profile()`
- reads a JSON profile file
- validates it via `ScraperProfile.model_validate`

`build_runtime_settings()`
- converts CLI args into `RuntimeSettings`
- sets:
  - output directory
  - output format
  - resume mode
  - sync mode
  - timeout

`main()`
- parses args
- loads profile
- builds runtime settings
- creates a `Crawler`
- runs the crawl

### Example command

```bash
python web_scraper.py --profile profiles/entrancegateway_syllabus.json --output-dir output --no-resume
```

### Sync example

```bash
python web_scraper.py --profile profiles/entrancegateway_notes.json --output-dir output --sync --no-resume
```

---

## Crawling Flow

### [crawler.py](scraper/crawler.py)

The crawler is queue-based.

### Core responsibilities

- normalize URLs
- enforce domain/include/exclude rules
- load previous checkpoint state
- maintain crawl queue
- detect list vs detail pages
- fetch HTML
- extract new URLs
- build documents from detail pages
- write outputs and checkpoint state

### URL normalization

The crawler preserves query parameters during normalization.

This is important for pagination such as:

- `?page=1`
- `?page=2`

Without this, paginated pages would collapse into the same canonical URL.

### Allowed URL logic

`is_allowed_url()` checks:

1. allowed domain
2. include regex patterns
3. exclude regex patterns

### Detail page detection

`looks_like_detail()` returns true if:

- the profile is PDF-based
- the URL ends with `.pdf`
- the URL matches `detail_url_keywords`
- or no detail keyword restriction exists

### HTML fetching

`fetch_html()` uses:

- HTTP fetch by default
- browser fetch in `browser` mode
- conditional browser fallback in `auto` mode

### Queue loading

`load_queue()` reads checkpoint state and restores:

- visited URLs
- queued URLs

If no checkpoint queue exists, it starts from profile `start_urls`.

### Main crawl loop

The loop continues while:

- queue still has URLs
- and `max_pages` is either unlimited (`null`) or not exceeded

For each URL:

1. normalize URL
2. skip visited/disallowed URLs
3. mark visited
4. increment page stats
5. decide if detail or list page
6. for detail pages:
   - fetch page
   - build document
   - append to in-memory list
   - append JSONL if not in sync mode
7. for list pages:
   - fetch page
   - extract detail URLs
   - extract pagination URLs
   - enqueue new URLs if depth limit allows
8. save checkpoint after each iteration

### Finalization

At the end of the crawl:

- aggregate export is written
- sync stats are returned from storage
- success log is printed

If `sync_mode` is on, the final log includes:

- added
- updated
- deleted
- unchanged

---

## Extraction Behavior

### [extractors.py](scraper/extractors.py)

This module is responsible for:

- parsing HTML into BeautifulSoup
- extracting list links
- extracting pagination links
- extracting content and metadata
- building final document objects

Important behavior already implemented in the project:

- `data-role` is treated as the primary contract
- `data-detail-uri` is preferred as canonical detail URL when available
- hidden `meta-*` blocks are used as fallback metadata sources
- SSR-first extraction is supported
- list/detail selectors are driven by profile config

For EntranceGateway this means the extractor can work with contracts like:

- `syllabus-link`
- `question-link`
- `note-link`
- `college-link`
- `blog-link`
- `training-link`
- `quiz-link`

and metadata blocks like:

- `meta-subject-info`
- `meta-note-info`
- `meta-question-info`
- `meta-college-info`
- `meta-course-info`
- `meta-blog-info`
- `meta-training-info`
- `meta-quiz-info`

---

## Storage and Output Model

### [storage.py](scraper/storage.py)

This module now manages:

- output directory creation
- JSONL output
- aggregate JSON output
- checkpoint persistence
- error persistence
- existing aggregate loading
- sync reconciliation

### Output paths

For a profile named `entrancegateway_syllabus`, storage creates:

- `output/entrancegateway_syllabus.jsonl`
- `output/entrancegateway_syllabus.json`
- `output/entrancegateway_syllabus_checkpoint.json`
- `output/entrancegateway_syllabus_errors.jsonl`

### Standard mode behavior

When `sync_mode=False`:

- documents are appended to JSONL during crawl
- aggregate JSON is written at the end
- checkpoint is maintained
- errors are written to error JSONL

### Sync mode behavior

When `sync_mode=True`:

- per-document JSONL append is skipped during crawl
- previous aggregate JSON is loaded if it exists
- current documents are keyed by stable identity
- previous and current documents are compared
- JSONL is rewritten from scratch to latest truth
- aggregate JSON is rewritten to latest truth
- `_meta.sync_stats` is included in aggregate output

### Stable identity

`document_key()` uses this priority:

1. `document["url"]`
2. `metadata["canonical_url"]`
3. `metadata["data_detail_uri"]`
4. `metadata["source_url"]`

This allows the scraper to match old and new versions of the same document.

### Change detection

`document_hash()` computes a SHA-256 hash of a normalized JSON serialization of the document.

This is used to detect whether a shared document is:

- unchanged
- updated

### Reconciliation result

`reconcile_documents()` computes:

- `added`
- `updated`
- `deleted`
- `unchanged`
- `missing_identity_previous`
- `missing_identity_current`

### Behavior when identity fields are missing

If a document is missing all supported identity fields:

- `url`
- `metadata.canonical_url`
- `metadata.data_detail_uri`
- `metadata.source_url`

then that document is still exported in the final output, but it cannot be matched reliably across runs during sync reconciliation.

Current behavior:

- it remains in exported `documents`
- it is excluded from key-based add/update/delete matching
- it is counted in `missing_identity_previous` or `missing_identity_current`
- aggregate metadata includes an `identity_resolution` section documenting this rule

### Current delete behavior

In sync mode, deleted records are **hard deleted** from the final aggregate output because only the latest crawl documents are written.

---

## Sync Mode Details

Sync mode is currently **opt-in** through the CLI:

```bash
--sync
```

### What it does now

If a previous aggregate file exists and sync mode is enabled:

- new records are added
- changed records are replaced
- missing old records are removed from final output
- documents without identity fields remain exported but are tracked separately in missing-identity stats
- sync stats are included in aggregate metadata and logs
- final sync logging uses defensive defaults so malformed stats do not crash the crawler

### Example use case

You scraped notes yesterday and saved:

- note A
- note B

Today the website contains:

- note A unchanged
- note B edited
- note C new
- note D deleted from site

After a `--sync` run:

- note A remains
- note B is updated
- note C is added
- note D disappears from the final aggregate output

---

## EntranceGateway Profiles

Profiles are stored in [profiles/](profiles/).

Currently available:

- [entrancegateway_syllabus.json](profiles/entrancegateway_syllabus.json)
- [entrancegateway_questions.json](profiles/entrancegateway_questions.json)
- [entrancegateway_notes.json](profiles/entrancegateway_notes.json)
- [entrancegateway_colleges.json](profiles/entrancegateway_colleges.json)
- [entrancegateway_courses.json](profiles/entrancegateway_courses.json)
- [entrancegateway_blogs.json](profiles/entrancegateway_blogs.json)
- [entrancegateway_trainings.json](profiles/entrancegateway_trainings.json)
- [entrancegateway_quiz.json](profiles/entrancegateway_quiz.json)

### Common profile characteristics

Most profiles now use:

- SSR-first selectors
- `data-role` contracts from `SCRAPER.md`
- query pagination
- `detail_url_keywords`
- `include_patterns`
- `exclude_patterns`
- `render_mode: "http"`
- `max_pages: null`
- `max_depth: 3`
- `request_delay_seconds: 0.4`

### Important effect of `max_pages: null`

There is no hard cap anymore. Crawling continues until:

- queue is exhausted
- or depth/domain/include/exclude rules stop more traversal

---

## Tests

Current tests live in [tests/](file:///home/rohan-shrestha/Desktop/eg/chatbot/tests).

### Existing test files

- [test_config.py](tests/test_config.py)
- [test_extractors.py](tests/test_extractors.py)
- [test_storage.py](tests/test_storage.py)

### What is covered now

`test_config.py`
- allowed domain defaulting
- selector list normalization
- runtime sync mode acceptance

`test_storage.py`
- sync mode runtime setting
- add/update/unchanged reconciliation
- deletion reconciliation
- JSONL rewrite expectation in sync mode

---

## Setup and Usage Docs

### [SETUP.md](SETUP.md)
Contains:

- environment setup
- dependency install
- profile execution commands
- output file explanation
- resume behavior
- frontend requirements
- troubleshooting

### [SCRAPER.md](SCRAPER.md)
Documents the intended frontend scraper contract, including:

- page roles
- list/detail roles
- hidden metadata roles
- pagination behavior
- verification commands

---

## Current Operational Commands

### Fresh run

```bash
python web_scraper.py --profile profiles/entrancegateway_syllabus.json --output-dir output --no-resume
```

### Resume run

```bash
python web_scraper.py --profile profiles/entrancegateway_syllabus.json --output-dir output
```

### Sync run

```bash
python web_scraper.py --profile profiles/entrancegateway_syllabus.json --output-dir output --sync --no-resume
```

### Run tests

```bash
pytest
```

---

## Current Limitations / Caveats

### 1. Sync mode is implemented in storage layer, but should still be validated end-to-end
The storage reconciliation logic is present, but a full real-site verification run is still recommended.

### 2. JSONL semantics differ by mode
- normal mode: append during crawl
- sync mode: rewrite at end as latest truth

### 3. Deletion depends on crawl completeness
If a sync crawl misses valid pages because of frontend breakage or selector mismatch, those records may be removed from output.

### 4. Browser mode exists but current profiles are primarily HTTP/SSR oriented
The current EntranceGateway profiles are optimized for SSR HTML contracts.

### 5. Stable identity depends on canonical document URLs
Best sync results happen when the frontend exposes stable `data-detail-uri` or canonical URLs.

### 6. Documents without identity fields cannot be reconciled reliably
Such documents are still exported, but they cannot participate in stable add/update/delete matching across runs and are reported in missing-identity stats.

### 7. Sync logging is defensive, but malformed stats still indicate a deeper bug
The crawler now defaults missing sync-stat fields to zero in the final log. That prevents a logging crash, but malformed sync-stat payloads should still be investigated.

---

## Current State Summary

The scraper is currently implemented as a modular, profile-driven scraping framework with:

- SSR-first extraction
- automatic detail discovery from list pages
- query pagination support
- unlimited crawl support
- checkpoint resume support
- structured aggregate and JSONL outputs
- sync mode for add/update/delete reconciliation
- EntranceGateway-specific profiles for all requested content areas

It is now substantially more production-ready than the original single-file scraper and is structured for further extension.
