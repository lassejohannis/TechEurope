#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PID=""
WEB_PID=""
BACKEND_LOG="${ROOT_DIR}/server/.dev-server.log"
BACKEND_HEALTH_URL="http://127.0.0.1:8000/api/health"
BACKEND_STARTUP_TIMEOUT_SECONDS=120
SERVER_DEPS_STAMP="${ROOT_DIR}/server/.venv/.deps-lock-hash"

find_listeners() {
  local port="$1"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
}

free_port() {
  local port="$1"
  local pids
  pids="$(find_listeners "${port}")"
  if [[ -z "${pids}" ]]; then
    return 0
  fi

  echo "Port ${port} is in use. Stopping existing listener(s):"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN || true
  echo "${pids}" | xargs kill 2>/dev/null || true
  sleep 1

  # If still alive, force stop.
  pids="$(find_listeners "${port}")"
  if [[ -n "${pids}" ]]; then
    echo "Force-stopping remaining listener(s) on port ${port}."
    echo "${pids}" | xargs kill -9 2>/dev/null || true
  fi
}

cleanup() {
  if [[ -n "${WEB_PID}" ]] && kill -0 "${WEB_PID}" 2>/dev/null; then
    kill "${WEB_PID}" 2>/dev/null || true
  fi
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

free_port 8000
free_port 5173

ensure_server_deps() {
  local lock_hash current_hash
  if [[ ! -f "${ROOT_DIR}/server/uv.lock" || ! -f "${ROOT_DIR}/server/pyproject.toml" ]]; then
    return 0
  fi
  if ! command -v shasum >/dev/null 2>&1; then
    return 0
  fi

  lock_hash="$(shasum "${ROOT_DIR}/server/uv.lock" "${ROOT_DIR}/server/pyproject.toml" | shasum | awk '{print $1}')"
  current_hash=""
  if [[ -f "${SERVER_DEPS_STAMP}" ]]; then
    current_hash="$(cat "${SERVER_DEPS_STAMP}" 2>/dev/null || true)"
  fi

  if [[ "${lock_hash}" != "${current_hash}" ]]; then
    echo "Dependency lock changed. Running 'uv sync' in server/ ..."
    (
      cd "${ROOT_DIR}/server"
      uv sync
    )
    mkdir -p "$(dirname "${SERVER_DEPS_STAMP}")"
    printf "%s" "${lock_hash}" > "${SERVER_DEPS_STAMP}"
  fi
}

ensure_server_deps

echo "Starting backend on :8000 and frontend on :5173"
echo "Backend log file: ${BACKEND_LOG}"
echo "Tip: live logs with: tail -f ${BACKEND_LOG}"

(
  cd "${ROOT_DIR}/server"
  if [[ -x "${ROOT_DIR}/server/.venv/bin/python" ]]; then
    PYTHONPATH=src "${ROOT_DIR}/server/.venv/bin/python" -m server.cli > "${BACKEND_LOG}" 2>&1
  else
    export UV_CACHE_DIR="${ROOT_DIR}/server/.uv-cache"
    uv run server > "${BACKEND_LOG}" 2>&1
  fi
) &
SERVER_PID=$!

# Start frontend immediately in parallel — no need to wait for backend.
(
  cd "${ROOT_DIR}/web"
  npm run dev -- --host 127.0.0.1
) &
WEB_PID=$!

# Wait briefly and fail fast when backend crashes at startup.
sleep 0.3
if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
  echo "Backend failed to start. Last log lines:"
  tail -n 80 "${BACKEND_LOG}" || true
  exit 1
fi

echo "Waiting for backend readiness at ${BACKEND_HEALTH_URL} ..."
ready=0
max_polls=$(( BACKEND_STARTUP_TIMEOUT_SECONDS * 5 ))
for ((i=1; i<=max_polls; i++)); do
  if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
    echo "Backend exited while waiting for readiness. Last log lines:"
    tail -n 80 "${BACKEND_LOG}" || true
    exit 1
  fi

  if curl -fsS "${BACKEND_HEALTH_URL}" >/dev/null 2>&1; then
    ready=1
    break
  fi

  sleep 0.2
done

if [[ "${ready}" -ne 1 ]]; then
  echo "Backend readiness timed out after ${BACKEND_STARTUP_TIMEOUT_SECONDS}s. Last log lines:"
  tail -n 80 "${BACKEND_LOG}" || true
  exit 1
fi

while true; do
  if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
    break
  fi
  if ! kill -0 "${WEB_PID}" 2>/dev/null; then
    break
  fi
  sleep 1
done

wait "${SERVER_PID}" 2>/dev/null || true
wait "${WEB_PID}" 2>/dev/null || true
