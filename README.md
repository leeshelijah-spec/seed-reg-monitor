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
- Filter unreviewed regulation/article tables by column with checkbox-driven pick lists
- Open news operations status from a topbar modal while keeping analysis panels focused
- Track updates through dated feature updates

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

## Latest Update

- Latest update: [2026-04-06](docs/feature-updates/2026-04-06.md)
- Removed the read-only/ngrok sharing flow and returned the app to a single editable dashboard mode
- Simplified templates and request handling by dropping read-only write-blocking branches
- Reworked the startup Python resolver to recreate `.venv` from a launchable base Python when needed
- Kept the one-time post-start sync, KPI tooltips, operations modal, and per-column review-table filters

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

## Edit Mode

Use the launcher below to run the dashboard with sync, review, keyword, and feedback actions enabled.

1. Start the dashboard:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_dashboard.ps1
```

Windows users can also double-click `start_dashboard.cmd` from the repository root.

If `.venv` is missing or broken, the launcher now tries to recreate it from a launchable base Python and reinstall `requirements.txt` automatically before starting the app.

If PowerShell still cannot find Python after a reinstall, set `PYTHON_EXE` explicitly for the launch session:

```powershell
$env:PYTHON_EXE = "C:\Path\To\python.exe"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_dashboard.ps1
```

When startup finishes, the launcher also runs one one-time `app.manual_sync` pass so regulation sync and Naver-news collection each execute once right after `Application startup complete`.

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

Feature update conventions are documented in [docs/feature-updates/README.md](docs/feature-updates/README.md).

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
