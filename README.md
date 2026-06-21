# Codex + GLM-5.2 Proxy

A lightweight local proxy that lets [OpenAI Codex CLI](https://github.com/openai/codex) use
[GLM-5.2](https://z.ai) via [Zhipu AI's API](https://open.bigmodel.cn).

## Architecture

```
Codex CLI ──── Responses API ────▶ glm_proxy.py :8787 ──── Chat API ────▶ Zhipu ────▶ GLM-5.2
```

The proxy translates Codex's [Responses API](https://platform.openai.com/docs/api-reference/responses)
calls into standard Chat Completions API calls that Zhipu understands.

## Features

- **Protocol translation**: Responses API ↔ Chat Completions API
- **Tool forwarding**: Converts Codex tool definitions from Responses format to function-calling format
- **Tool call extraction**: Parses `tool_calls` from model responses back into Responses API format
- **SSE streaming**: Server-Sent Events streaming support for real-time output
- **Model metadata**: Provides full model capability info required by Codex
- **Encoding safe**: Handles UTF-8 and latin-1 request bodies
- **Zero dependencies**: Standard library only (Python 3.8+)

## Quick Start

### 1. Get an API key

Register at [open.bigmodel.cn](https://open.bigmodel.cn) and create an API key.

### 2. Start the proxy

```bash
export GLM_***EY=your_z...# bash / zsh
python glm_proxy.py

# Windows cmd:
set GLM_API_KEY=your_zhipu_key
python glm_proxy.py
```

The proxy listens on `http://127.0.0.1:8787`.

### 3. Verify

```bash
curl http://127.0.0.1:8787/health
# {"status": "ok", "provider": "zhipu"}

curl http://127.0.0.1:8787/models
# {"object": "list", "models": [{"id": "glm-5.2", ...}]}
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

See `examples/codex_config.toml` for a complete example.

### 5. Use Codex

```bash
codex --yolo exec "your coding task here"
```

## Known Limitations

- **Tool calling**: GLM-5.2 has limited function-calling ability through the Zhipu Chat API.
  Codex sessions consuming 8K+ tokens may not produce actual tool calls.
- **Reasoning levels**: The model's `reasoning_content` field may mix with `content`,
  requiring sufficient `max_tokens` (recommend 16K+) for the model to complete
  reasoning before outputting the answer.

## Endpoints

| Path | Method | Purpose |
|------|--------|---------|
| `/health` | GET | Health check |
| `/models` | GET | Model list (Codex compatible) |
| `/v1/chat/completions` | POST | Chat Completions proxy |
| `/responses` | POST | Responses API → Chat API conversion |
| `/v1/responses` | POST | Same, with `/v1/` prefix |

## License

MIT
