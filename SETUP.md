# Scraper Setup Guide

## 1. Open the project

```bash
cd yourfilepath
```

## 2. Create a virtual environment

```bash
python3 -m venv .venv
```

## 3. Activate the virtual environment

```bash
source .venv/bin/activate
```

## 4. Install dependencies

```bash
pip install -r requirements.txt
```

If installation times out, install the core packages first:

```bash
pip install requests beautifulsoup4 lxml pydantic tenacity loguru pytest
```

Optional for JavaScript-heavy websites:

```bash
pip install playwright
playwright install
```

## 5. Scraper profiles

Profiles are stored in:

```text
profiles/
```

Available EntranceGateway profiles:

- `profiles/entrancegateway_syllabus.json`
- `profiles/entrancegateway_questions.json`
- `profiles/entrancegateway_notes.json`
- `profiles/entrancegateway_colleges.json`
- `profiles/entrancegateway_courses.json`
- `profiles/entrancegateway_blogs.json`
- `profiles/entrancegateway_trainings.json`
- `profiles/entrancegateway_quiz.json`

## 6. Run the scraper

General format:

```bash
python web_scraper.py --profile <profile-path> --output-dir output --no-resume
```

Examples:

### Syllabus

```bash
python web_scraper.py --profile profiles/entrancegateway_syllabus.json --output-dir output --no-resume
```

### Old Questions

```bash
python web_scraper.py --profile profiles/entrancegateway_questions.json --output-dir output --no-resume
```

### Notes

```bash
python web_scraper.py --profile profiles/entrancegateway_notes.json --output-dir output --no-resume
```

### Colleges

```bash
python web_scraper.py --profile profiles/entrancegateway_colleges.json --output-dir output --no-resume
```

### Courses

```bash
python web_scraper.py --profile profiles/entrancegateway_courses.json --output-dir output --no-resume
```

### Blogs

```bash
python web_scraper.py --profile profiles/entrancegateway_blogs.json --output-dir output --no-resume
```

### Trainings

```bash
python web_scraper.py --profile profiles/entrancegateway_trainings.json --output-dir output --no-resume
```

### Quiz

```bash
python web_scraper.py --profile profiles/entrancegateway_quiz.json --output-dir output --no-resume
```

## 7. Output files

The scraper creates the output directory automatically.

Generated files usually include:

- `<profile-name>.json`
- `<profile-name>.jsonl`
- `<profile-name>_checkpoint.json`
- `<profile-name>_errors.jsonl`

Example:

```text
output/entrancegateway_syllabus.json
output/entrancegateway_syllabus.jsonl
output/entrancegateway_syllabus_checkpoint.json
output/entrancegateway_syllabus_errors.jsonl
```

## 8. Resume behavior

Default behavior resumes from checkpoint files.

Use this for a fresh run:

```bash
python web_scraper.py --profile profiles/entrancegateway_syllabus.json --output-dir output --no-resume
```

Or delete a checkpoint manually:

```bash
rm output/entrancegateway_syllabus_checkpoint.json
```

## 9. How crawling works

You only need to provide the list page in the profile.

The scraper will automatically:

1. open the list page
2. discover detail URLs from `data-detail-uri`, `href`, or `data-href`
3. follow pagination links
4. crawl detail pages
5. save extracted documents

## 10. Frontend requirements

For best results, the frontend should server-render:

- `data-role="page-content"`
- `data-role="page-title"`
- list item roles like `note-item`, `question-item`, `course-item`
- link roles like `note-link`, `question-link`, `syllabus-link`
- canonical `data-detail-uri`
- pagination links such as `?page=1`, `?page=2`
- hidden metadata blocks like `meta-note-info`, `meta-question-info`, `meta-subject-info`

## 11. Troubleshooting

### File not found for profile

Use a real profile path:

```bash
python web_scraper.py --profile profiles/entrancegateway_syllabus.json --output-dir output
```

### Nothing gets scraped

Check:

- the page contains SSR HTML
- list/detail links exist in raw HTML
- `data-detail-uri` or `href` is present
- old checkpoints are not blocking a fresh run

### Re-run from scratch

```bash
python web_scraper.py --profile profiles/entrancegateway_syllabus.json --output-dir output --no-resume
```

### Validate output quickly

```bash
head -n 5 output/entrancegateway_syllabus.jsonl
python -m json.tool output/entrancegateway_syllabus.json | head -n 80
```

## 12. Optional testing

```bash
pytest
```
