#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! curl -s http://127.0.0.1:8787/health >/dev/null 2>&1; then
    echo "[Codex Proxy] Starting..."
    python "${SCRIPT_DIR}/../glm_proxy.py" &
    for i in $(seq 1 10); do
        sleep 1
        curl -s http://127.0.0.1:8787/health >/dev/null 2>&1 && break
    done
    echo "[Codex Proxy] Ready"
fi

exec codex "$@"
