# Seed Regulation Monitor

[한국어 README 보기](README.ko.md)

Seed Regulation Monitor is a FastAPI-based dashboard for collecting, classifying, and reviewing regulatory changes relevant to the seed industry.

## Author

- Lee, Seunghwan
- [leesh.elijah@gmail.com](mailto:leesh.elijah@gmail.com)

## Features

- Collect promulgated laws and administrative rules
- Collect legislative notice candidates
- Classify each item by severity, category, and related department
- Review detailed amendment reasons on regulation detail pages
- Record action status and review notes
- Maintain a Markdown-based feature update log

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
```

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

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
copy .env.example .env
```

Check at least these values in `.env`:

- `KOREAN_LAW_MCP_DIR`
- `DB_PATH`
- `ENABLE_SCHEDULER`

If you want to use alert delivery, create `config/alert-recipients.json` from `config/alert-recipients.example.json`.

### 4. Run the app

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

- Dashboard: [http://127.0.0.1:8010/](http://127.0.0.1:8010/)
- Health check: [http://127.0.0.1:8010/health](http://127.0.0.1:8010/health)

## Manual Sync

```bash
python -m app.manual_sync
```

## Acknowledgements

This project uses and builds on ideas from [korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp) by [@chrisryugj](https://github.com/chrisryugj).

Thanks for making Korean law data access easier to explore and integrate.

## License

This project is licensed under the [MIT License](LICENSE).
