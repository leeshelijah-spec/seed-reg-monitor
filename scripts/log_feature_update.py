from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent.parent
FEATURE_UPDATE_DIR = BASE_DIR / "docs" / "feature-updates"
TIMEZONE = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append a dated markdown entry describing completed feature updates."
    )
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to today in Asia/Seoul.")
    parser.add_argument("--title", required=True, help="Short title for this update entry.")
    parser.add_argument(
        "--change",
        action="append",
        required=True,
        help="One change item to append. Repeat this option for multiple bullets.",
    )
    return parser.parse_args()


def resolve_date(raw_date: str | None) -> str:
    if raw_date:
        return raw_date
    return datetime.now(TIMEZONE).date().isoformat()


def build_entry(now: datetime, title: str, changes: list[str]) -> str:
    lines = [f"## {now.strftime('%H:%M')} {title}", ""]
    lines.extend(f"- {change}" for change in changes)
    lines.append("")
    return "\n".join(lines)


def ensure_header(path: Path, target_date: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {target_date}\n\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    target_date = resolve_date(args.date)
    now = datetime.now(TIMEZONE)
    target_path = FEATURE_UPDATE_DIR / f"{target_date}.md"

    ensure_header(target_path, target_date)
    with target_path.open("a", encoding="utf-8") as file:
        file.write(build_entry(now, args.title.strip(), [item.strip() for item in args.change if item.strip()]))


if __name__ == "__main__":
    main()
