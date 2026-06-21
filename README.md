# Codex + GLM-5.2 Proxy

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-green.svg)](https://www.python.org/)

> Make **OpenAI Codex CLI** work with **GLM-5.2** — Zhipu AI's SOTA coding model.
> A lightweight local protocol proxy that translates Codex's Responses API into
> Zhipu's Chat Completions API. **Zero dependencies — standard library only.**

## Why?

Codex CLI only supports OpenAI models natively. GLM-5.2 is a 753B-parameter
open-weights model that beats GPT-5.5 on coding benchmarks at 1/6 the cost.
This proxy bridges the two, letting you use Codex with GLM-5.2 through Zhipu's API.

**Verified working**: Codex successfully creates files, writes code, and executes
commands through GLM-5.2 via this proxy.

## Quick Start

### 1. Install Codex CLI
```bash
npm install -g @openai/codex
```

### 2. Get a Zhipu API Key
Register at [open.bigmodel.cn](https://open.bigmodel.cn) → API Keys → Create.

### 3. Clone & Run the Proxy
```bash
git clone https://github.com/KevinSHH/codex-glm-proxy.git
cd codex-glm-proxy

# Linux / macOS
export GLM_API_KEY=your_key_here
python glm_proxy.py

# Windows (cmd)
set GLM_API_KEY=your_key_here
python glm_proxy.py

# Windows (PowerShell)
$env:GLM_API_KEY = "your_key_here"
python glm_proxy.py
```

### 4. Configure Codex
Add to `~/.codex/config.toml`:
```toml
model = "glm-5.2"
model_provider = "glm-proxy"

[model_providers.glm-proxy]
name = "GLM Proxy"
wire_api = "responses"
base_url = "http://127.0.0.1:8787"
env_key = "DUMMY_API_KEY"
```

### 5. Start Coding!
```bash
codex --yolo exec "Write a FastAPI server with user authentication"
```

## Architecture

```
┌──────────┐  Responses API   ┌───────────────┐  Chat API   ┌──────────────┐
│  Codex   │ ───────────────▶ │  glm_proxy.py │ ──────────▶ │  Zhipu AI    │
│   CLI    │ ◀─────────────── │    :8787      │ ◀────────── │  (GLM-5.2)   │
└──────────┘  SSE/JSON stream └───────────────┘  JSON resp  └──────────────┘
```

The proxy handles:
- **Protocol translation**: Responses API ↔ Chat Completions
- **Tool conversion**: Responses format → function-calling format
- **Thinking control**: Disables GLM-5.2's mandatory CoT (critical for tool calls)
- **SSE streaming**: Server-Sent Events with `function_call` events
- **Model metadata**: Full capability info for Codex compatibility

## Auto-Start Wrapper

Drop one of these scripts in your PATH to automatically start the proxy before Codex:

**Windows (`codex-glm.bat`):**
```bat
@echo off
REM Start proxy if not already running
curl -s http://127.0.0.1:8787/health >nul 2>&1
if errorlevel 1 (
    echo Starting GLM Proxy...
    start /B pythonw "%~dp0\glm_proxy.py"
    timeout /t 3 /nobreak >nul
)
codex %*
```

**Linux/macOS (`codex-glm`):**
```bash
#!/bin/bash
# Start proxy if not already running
curl -s http://127.0.0.1:8787/health >/dev/null 2>&1 || {
    echo "Starting GLM Proxy..."
    python "$(dirname "$0")/glm_proxy.py" &
    sleep 2
}
exec codex "$@"
```

Then use `codex-glm` instead of `codex`:
```bash
codex-glm --yolo exec "Build a React dashboard"
```

## Key Fixes

This proxy includes critical patches discovered through extensive debugging:

| Issue | Symptom | Fix |
|-------|---------|-----|
| **Forced thinking** | Reasoning consumes all tokens; tool calls never appear | `enable_thinking: False` |
| **Missing reasoning field** | Codex doesn't send `reasoning` param; fix never triggers | Fallback when `effort` is empty |
| **SSE without function_call** | Streaming only emits text events; tool calls lost | Added `function_call` event support in SSE stream |
| **Proxy crash on disconnect** | Codex reports "stream disconnected before completion"; proxy process dead | ThreadingHTTPServer + socket error handling in `_sse_stream` + `handle_one_request` override |

### Debug Logging (Optional)

Set `GLM_PROXY_DEBUG` to a file path to enable request/response logging:
```bash
# Windows
set GLM_PROXY_DEBUG=C:\Users\you\.codex\proxy_debug.log
python glm_proxy.py

# Linux/macOS
export GLM_PROXY_DEBUG=/tmp/proxy_debug.log
python glm_proxy.py
```

## API Endpoints

| Path | Method | Purpose |
|------|--------|---------|
| `/health` | GET | Health check (`{"status":"ok","provider":"zhipu"}`) |
| `/models` | GET | Model list (Codex-compatible format) |
| `/v1/chat/completions` | POST | Direct Chat Completions proxy |
| `/responses` | POST | Responses API → Chat API conversion |
| `/v1/responses` | POST | Same with `/v1/` prefix |

## Limitations

- **Looping**: Codex may loop on simple tasks — this is a Codex/model interaction issue,
  not a proxy bug. The file IS created correctly.
- **Coding endpoint**: The `/api/coding/paas/v4` endpoint requires a separate Zhipu
  subscription plan. This proxy uses the general `/api/paas/v4` endpoint.
- **Reasoning levels**: When thinking is enabled, GLM-5.2 uses significant tokens for
  reasoning before outputting content. The proxy disables this by default.

## Changelog

### v5.2 (Jun 2026)
- **Crash-resistant**: `ThreadingHTTPServer` + `handle_one_request` override + `_sse_stream` socket error handling
- Client disconnects mid-stream no longer kill the proxy process
- Debug logging made optional via `GLM_PROXY_DEBUG` env var
- Security: removed hardcoded API key placeholder

### v5.1 (Jun 2026)
- Initial public release: Responses API → Chat API protocol translation
- `enable_thinking: False` fix for tool calling
- SSE streaming with `function_call` event support

## Related Projects

- [GodeX](https://github.com/Ahoo-Wang/Godex) — Multi-provider Codex proxy (Go/TS)
- [opencodex](https://github.com/lidge-jun/opencodex) — Universal Codex proxy (TS)
- [GLM-5.2](https://github.com/zai-org/GLM-5) — Official GLM-5.2 model weights

## License

MIT © 2026
