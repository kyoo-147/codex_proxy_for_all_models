#!/bin/bash
# ============================================================
# codex-glm — Auto-start GLM Proxy + launch Codex
# ============================================================
# Usage: ./codex-glm [codex args...]
# Or: symlink to /usr/local/bin/codex-glm
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Start proxy if not already running
if ! curl -s http://127.0.0.1:8787/health >/dev/null 2>&1; then
    echo "[GLM Proxy] Starting..."
    python "${SCRIPT_DIR}/glm_proxy.py" &
    # Wait for proxy to be ready (max 10s)
    for i in $(seq 1 10); do
        sleep 1
        curl -s http://127.0.0.1:8787/health >/dev/null 2>&1 && break
    done
    echo "[GLM Proxy] Ready"
fi

exec codex "$@"
