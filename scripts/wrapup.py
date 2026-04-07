from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent.parent
README_PATH = BASE_DIR / "README.md"
README_KO_PATH = BASE_DIR / "README.ko.md"
FEATURE_UPDATE_DIR = BASE_DIR / "docs" / "feature-updates"
TIMEZONE = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append a dated feature update, refresh README latest update, and optionally create a git commit."
    )
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to today in Asia/Seoul.")
    parser.add_argument("--title", help="Short title for the feature update entry.")
    parser.add_argument(
        "--change",
        action="append",
        help="One change bullet for the feature update. Repeat this option for multiple bullets.",
    )
    parser.add_argument("--commit-message", help="Commit message. Defaults to prompting.")
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Update docs and stage files, but do not create a commit.",
    )
    return parser.parse_args()


def prompt_nonempty(label: str) -> str:
    while True:
        value = input(label).strip()
        if value:
            return value
        print("A value is required.")


def prompt_changes() -> list[str]:
    print("Enter change bullets. Press Enter on an empty line when finished.")
    changes: list[str] = []
    while True:
        value = input(f"Change {len(changes) + 1}: ").strip()
        if not value:
            if changes:
                return changes
            print("At least one change bullet is required.")
            continue
        changes.append(value)


def resolve_date(raw_date: str | None) -> str:
    if raw_date:
        return raw_date
    return datetime.now(TIMEZONE).date().isoformat()


def ensure_feature_update_file(target_date: str) -> Path:
    path = FEATURE_UPDATE_DIR / f"{target_date}.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {target_date}\n\n", encoding="utf-8")
    return path


def append_feature_update(target_date: str, title: str, changes: list[str]) -> None:
    now = datetime.now(TIMEZONE)
    path = ensure_feature_update_file(target_date)
    lines = [f"## {now.strftime('%H:%M')} {title}", ""]
    lines.extend(f"- {change}" for change in changes)
    lines.append("")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def replace_section(content: str, heading: str, new_lines: list[str]) -> str:
    lines = content.splitlines()

    start_index = None
    end_index = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start_index = index
            continue
        if start_index is not None and index > start_index and line.startswith("## "):
            end_index = index
            break

    if start_index is None:
        raise RuntimeError(f"README section '{heading}' was not found.")
    if end_index is None:
        end_index = len(lines)

    merged = lines[:start_index] + new_lines + lines[end_index:]
    return "\n".join(merged) + "\n"


def update_readme_latest(target_date: str, changes: list[str]) -> None:
    latest_lines = [
        "## Latest Update",
        "",
        f"- Latest update: [{target_date}](docs/feature-updates/{target_date}.md)",
    ]
    latest_lines.extend(f"- {change}" for change in changes[:5])
    latest_lines.append("")
    updated = replace_section(README_PATH.read_text(encoding="utf-8"), "## Latest Update", latest_lines)
    README_PATH.write_text(updated, encoding="utf-8")


def update_readme_ko_latest(target_date: str, changes: list[str]) -> None:
    latest_lines = [
        "## 최신 업데이트",
        "",
        f"- 최신 업데이트: [{target_date}](docs/feature-updates/{target_date}.md)",
    ]
    latest_lines.extend(f"- {change}" for change in changes[:5])
    latest_lines.append("")
    updated = replace_section(README_KO_PATH.read_text(encoding="utf-8"), "## 최신 업데이트", latest_lines)
    README_KO_PATH.write_text(updated, encoding="utf-8")


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=BASE_DIR,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def stage_all() -> None:
    result = run_git("add", "-A")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git add failed")


def has_staged_changes() -> bool:
    result = run_git("diff", "--cached", "--quiet")
    return result.returncode == 1


def commit_changes(message: str) -> None:
    result = run_git("commit", "-m", message)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git commit failed")


def main() -> int:
    args = parse_args()
    target_date = resolve_date(args.date)
    title = args.title.strip() if args.title else prompt_nonempty("Update title: ")
    changes = [item.strip() for item in args.change if item and item.strip()] if args.change else prompt_changes()

    if args.commit_message and args.commit_message.strip():
        commit_message = args.commit_message.strip()
    else:
        commit_message = prompt_nonempty("Commit message: ")

    append_feature_update(target_date, title, changes)
    update_readme_latest(target_date, changes)
    update_readme_ko_latest(target_date, changes)
    stage_all()

    if not has_staged_changes():
        print("No staged changes were detected after wrap-up.")
        return 0

    if args.no_commit:
        print("Wrap-up complete. Changes are staged but not committed.")
        return 0

    commit_changes(commit_message)
    print("Wrap-up complete. Feature update, README, and commit are ready.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nWrap-up cancelled.")
        raise SystemExit(1)
    except Exception as exc:  # pragma: no cover
        print(f"Wrap-up failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
