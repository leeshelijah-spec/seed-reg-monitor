#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXE=""

if [[ -x "${PROJECT_ROOT}/.venv/Scripts/python.exe" ]]; then
  PYTHON_EXE="${PROJECT_ROOT}/.venv/Scripts/python.exe"
elif command -v python >/dev/null 2>&1; then
  PYTHON_EXE="$(command -v python)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_EXE="$(command -v python3)"
else
  echo "Python executable not found."
  echo "Create .venv or install Python, then run ./refinelogic.sh again."
  exit 1
fi

exec "${PYTHON_EXE}" "${PROJECT_ROOT}/scripts/refinelogic.py" "$@"
