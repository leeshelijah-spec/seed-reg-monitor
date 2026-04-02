# Seed Regulation Monitor

[한국어 README 보기](README.ko.md)

Seed Regulation Monitor is a FastAPI dashboard for monitoring seed-industry regulations and Naver-news-based industry trends in one place.

## Author

- Lee, Seunghwan

## Features

- Collect promulgated laws and administrative rules
- Collect legislative notice candidates
- Classify each item by severity, category, and related department
- Review detailed amendment reasons on regulation detail pages
- Record action status and review notes
- Collect, deduplicate, and analyze Naver news for seed-industry trends
- Capture article feedback, keyword management, and collection logs
- Track updates through release notes

## Stack

- FastAPI
- Jinja2
- Chart.js
- SQLite
- APScheduler

## Project Structure

```text
app/
  main.py
  routes/
  services/
  templates/
  static/
config/
data/
docs/
scripts/
tests/
```

## Latest Release

- Latest release: [2026-04-02](docs/releases/2026-04-02.md)
- Removed the hero box and moved the descriptive copy under `Seed Regulation Monitor`
- Rearranged regulation and news KPI cards into separate 2x2 layouts
- Combined news filters and keyword admin controls into a toggle panel opened by the `필터` button
- Removed the top-important-articles block and kept charts, executive summary, and operations in 1x2 rows

## Quick Start

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

Windows:

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

macOS / Linux:

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
copy .env.example .env
copy .env.example .env.local
```

Use `.env` for shared defaults and `.env.local` for per-developer secrets.

Minimum required values:

- `KOREAN_LAW_MCP_DIR`
- `DB_PATH`
- `ENABLE_SCHEDULER`

News module values:

- `NAVER_CLIENT_ID`
- `NAVER_CLIENT_SECRET`
- `NEWS_KEYWORDS_PATH`
- `NEWS_SCHEDULER_HOUR`
- `NEWS_SCHEDULER_MINUTE`

Do not commit Naver credentials. Each developer should obtain their own keys from the [Naver Developers portal](https://developers.naver.com/products/intro/plan/plan.md).

If you want a file-based keyword seed, copy `config/news-keywords.example.json` to `config/news-keywords.json`.

If you want alert delivery, create `config/alert-recipients.json` from `config/alert-recipients.example.json`.

### 4. Run the app

Windows:

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

macOS / Linux:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

If you are not in an activated virtual environment, prefer `.venv\Scripts\python -m uvicorn ...` instead of relying on a global `uvicorn` command.

- Dashboard: [http://127.0.0.1:8010/](http://127.0.0.1:8010/)
- Health check: [http://127.0.0.1:8010/health](http://127.0.0.1:8010/health)

## Manual Sync

Full manual sync:

```bash
.venv\Scripts\python -m app.manual_sync
```

Load sample news data:

```bash
.venv\Scripts\python scripts/seed_sample_news.py
```

Run tests:

```bash
.venv\Scripts\python -m unittest discover -s tests
```

## News Module Layout

- `app/services/naver_news.py`: Naver Search News API client
- `app/services/news_ingestion.py`: collection, cleanup, dedupe, and persistence
- `app/services/news_analysis.py`: topic, impact, urgency, and action analysis
- `app/services/news_dashboard.py`: KPI, filters, trends, and executive summary aggregation
- `app/services/news_keywords.py`: keyword seeding and admin management

Architecture notes are documented in [docs/news-dashboard-architecture.md](docs/news-dashboard-architecture.md).

Release note conventions are documented in [docs/releases/README.md](docs/releases/README.md).

## Sample Data

- Sample payload: `docs/samples/naver-news-sample.json`
- Seeder script: `scripts/seed_sample_news.py`

## Notes

- `.env`, `.env.local`, `config/news-keywords.json`, and `data/*.db` are gitignored.
- News deduplication is based on `originallink` via `duplicate_hash`.
- When the same article is matched by multiple keywords, they are merged into `matched_keywords`.

## Acknowledgements

This project uses and builds on ideas from [korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp) by [@chrisryugj](https://github.com/chrisryugj).

Thanks for making Korean law data access easier to explore and integrate.

## License

This project is licensed under the [MIT License](LICENSE).
