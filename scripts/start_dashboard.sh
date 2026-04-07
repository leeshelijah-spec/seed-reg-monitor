#!/usr/bin/env bash

set -euo pipefail

port=8010
bind_host="127.0.0.1"
reload=0

usage() {
  cat <<'EOF'
Usage: ./scripts/start_dashboard.sh [--port PORT] [--bind-host HOST] [--reload]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      port="${2:-}"
      shift 2
      ;;
    --bind-host)
      bind_host="${2:-}"
      shift 2
      ;;
    --reload)
      reload=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
venv_root="${repo_root}/.venv"
venv_python="${venv_root}/Scripts/python.exe"
temp_root="${repo_root}/.tmp"

mkdir -p "${temp_root}"
export TEMP="${temp_root}"
export TMP="${temp_root}"
export TMPDIR="${temp_root}"
export PYTHONIOENCODING="utf-8"
export PYTHONUTF8="1"
export PYTHONUNBUFFERED="1"

trim_quotes() {
  local value="${1:-}"
  value="${value%\"}"
  value="${value#\"}"
  printf '%s' "${value}"
}

to_unix_path() {
  local value
  value="$(trim_quotes "${1:-}")"
  if [[ -z "${value}" ]]; then
    return 1
  fi
  cygpath -u "${value}" 2>/dev/null || printf '%s\n' "${value}"
}

test_python_launchable() {
  local python_exe="${1:-}"
  [[ -n "${python_exe}" && -f "${python_exe}" ]] || return 1
  "${python_exe}" -c "import sys" >/dev/null 2>&1
}

get_pyvenv_setting() {
  local config_path="${1}"
  local key="${2}"
  [[ -f "${config_path}" ]] || return 1
  awk -F' = ' -v wanted="${key}" '$1 == wanted { print $2; exit }' "${config_path}" | tr -d '\r'
}

find_base_python() {
  local pyvenv_cfg="${venv_root}/pyvenv.cfg"
  local home_dir=""
  local config_executable=""
  local local_programs=""
  local py_launcher=""
  declare -A seen=()
  local candidates=()
  local candidate=""

  if [[ -n "${LOCALAPPDATA:-}" ]]; then
    local_programs="$(to_unix_path "${LOCALAPPDATA}")/Programs/Python"
  fi

  home_dir="$(get_pyvenv_setting "${pyvenv_cfg}" "home" || true)"
  config_executable="$(get_pyvenv_setting "${pyvenv_cfg}" "executable" || true)"

  [[ -n "${PYTHON_EXE:-}" ]] && candidates+=("$(to_unix_path "${PYTHON_EXE}" 2>/dev/null || printf '%s' "${PYTHON_EXE}")")
  [[ -n "${config_executable}" ]] && candidates+=("$(to_unix_path "${config_executable}")")
  [[ -n "${home_dir}" ]] && candidates+=("$(to_unix_path "${home_dir}")/python.exe")
  candidates+=("$(to_unix_path 'C:\py\python.exe' 2>/dev/null || printf '%s' 'C:/py/python.exe')")

  if [[ -n "${local_programs}" ]]; then
    candidates+=(
      "${local_programs}/Python313/python.exe"
      "${local_programs}/Python312/python.exe"
      "${local_programs}/Python311/python.exe"
      "${local_programs}/Python310/python.exe"
    )
  fi

  if command -v python >/dev/null 2>&1; then
    candidates+=("$(command -v python)")
  fi

  if command -v python.exe >/dev/null 2>&1; then
    candidates+=("$(command -v python.exe)")
  fi

  if command -v py >/dev/null 2>&1; then
    py_launcher="$(command -v py)"
    while IFS= read -r candidate; do
      [[ -n "${candidate}" && "${candidate}" != -* ]] || continue
      candidates+=("$(to_unix_path "${candidate}")")
    done < <("${py_launcher}" -0p 2>/dev/null || true)
  fi

  for candidate in "${candidates[@]}"; do
    [[ -n "${candidate}" ]] || continue
    if [[ -n "${seen[${candidate}]:-}" ]]; then
      continue
    fi
    seen["${candidate}"]=1
    if test_python_launchable "${candidate}"; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

ensure_venv_requirements() {
  local base_python="${1}"
  local project_python="${2}"

  if "${project_python}" -c "import fastapi, uvicorn, apscheduler, dotenv, jinja2" >/dev/null 2>&1; then
    return 0
  fi

  printf 'Installing dashboard dependencies into .venv...\n'
  "${base_python}" -m pip --python "${project_python}" install -r "${repo_root}/requirements.txt"
}

rebuild_virtualenv() {
  local base_python="${1}"

  if [[ -d "${venv_root}" ]]; then
    printf 'Existing .venv is not usable. Recreating it with %s\n' "${base_python}" >&2
    rm -rf "${venv_root}"
  fi

  printf 'Creating virtual environment at %s\n' "${venv_root}"
  "${base_python}" -m venv "${venv_root}" --without-pip

  if ! test_python_launchable "${venv_python}"; then
    printf '.venv was recreated, but %s is still not launchable.\n' "${venv_python}" >&2
    return 1
  fi

  ensure_venv_requirements "${base_python}" "${venv_python}"
}

resolve_project_python() {
  local base_python=""

  if test_python_launchable "${venv_python}"; then
    base_python="$(find_base_python || true)"
    if [[ -n "${base_python}" ]]; then
      ensure_venv_requirements "${base_python}" "${venv_python}"
    fi
    printf '%s\n' "${venv_python}"
    return 0
  fi

  base_python="$(find_base_python || true)"
  if [[ -z "${base_python}" ]]; then
    cat >&2 <<'EOF'
Could not find a launchable Python interpreter.
Set PYTHON_EXE to your Python path or install Python so it is reachable from Git Bash, then rerun:
  ./scripts/start_dashboard.sh
EOF
    return 1
  fi

  rebuild_virtualenv "${base_python}"
  printf '%s\n' "${venv_python}"
}

python_exe="$(resolve_project_python)"

cd "${repo_root}"

if [[ "${reload}" -eq 1 ]]; then
  printf 'Starting dashboard with live reload on http://%s:%s\n' "${bind_host}" "${port}"
else
  printf 'Starting dashboard on http://%s:%s\n' "${bind_host}" "${port}"
fi

uvicorn_args=(
  -m uvicorn
  app.main:app
  --app-dir "${repo_root}"
  --host "${bind_host}"
  --port "${port}"
)

if [[ "${reload}" -eq 1 ]]; then
  uvicorn_args+=(--reload --reload-dir "${repo_root}")
fi

startup_sync_triggered=0
uvicorn_fifo="${temp_root}/uvicorn-output.fifo"
rm -f "${uvicorn_fifo}"
mkfifo "${uvicorn_fifo}"

cleanup() {
  rm -f "${uvicorn_fifo}"
}

trap cleanup EXIT

"${python_exe}" "${uvicorn_args[@]}" >"${uvicorn_fifo}" 2>&1 &
uvicorn_pid=$!

while IFS= read -r line; do
  printf '%s\n' "${line}"

  if [[ "${startup_sync_triggered}" -eq 0 && "${line}" == *"Application startup complete"* ]]; then
    startup_sync_triggered=1
    printf '\nApplication startup complete detected. Running one-time regulation/news sync...\n'

    if "${python_exe}" -m app.manual_sync; then
      printf 'One-time startup sync finished.\n\n'
    else
      sync_exit=$?
      printf 'Warning: One-time startup sync exited with code %s.\n\n' "${sync_exit}" >&2
    fi
  fi
done <"${uvicorn_fifo}"

wait "${uvicorn_pid}"
exit $?
