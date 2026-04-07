#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export PYTHONIOENCODING=UTF-8
export PYTHONUTF8=1

if [[ -x "${PROJECT_ROOT}/.venv/Scripts/python.exe" ]]; then
  PYTHON_EXE="${PROJECT_ROOT}/.venv/Scripts/python.exe"
elif command -v python >/dev/null 2>&1; then
  PYTHON_EXE="$(command -v python)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_EXE="$(command -v python3)"
else
  echo "Python executable not found. Create .venv or install Python first."
  exit 1
fi

exec "${PYTHON_EXE}" "${PROJECT_ROOT}/scripts/wrapup.py" "$@"
