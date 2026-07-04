# Provider Guide

This proxy is designed for upstreams that expose:

- `POST /v1/chat/completions`
- bearer-token authentication
- JSON payloads close to the OpenAI Chat Completions shape

## Required variables

- `CODEX_PROXY_UPSTREAM_BASE_URL`
- `CODEX_PROXY_UPSTREAM_API_KEY`
- `CODEX_PROXY_UPSTREAM_MODEL`

## Optional variables

- `CODEX_PROXY_PROVIDER_LABEL`
- `CODEX_PROXY_LISTEN_HOST`
- `CODEX_PROXY_LISTEN_PORT`
- `CODEX_PROXY_EXTRA_HEADERS`
- `CODEX_PROXY_CONTEXT_WINDOW`
- `CODEX_PROXY_MAX_OUTPUT_TOKENS`
- `CODEX_PROXY_DEBUG_LOG`

## Example providers

### NVIDIA Build

- Base URL: `https://integrate.api.nvidia.com/v1`
- Models: browse [build.nvidia.com/models](https://build.nvidia.com/models)

### Ollama

- Base URL: `http://127.0.0.1:11434/v1`
- API key can be any placeholder string

### LM Studio

- Base URL often `http://127.0.0.1:1234/v1`

### vLLM

- Base URL often `http://127.0.0.1:8000/v1`

### SGLang

- Base URL depends on your server

### OpenRouter

- Base URL: `https://openrouter.ai/api/v1`
- May need extra headers like `HTTP-Referer` and `X-Title`

## Choosing good upstreams

Best fits:

- good chat-completions compatibility
- stable tool-calling
- decent context window
- predictable rate limits

For low-cost local testing:

- Ollama
- LM Studio

For hosted experimentation:

- NVIDIA Build
- OpenRouter
- DeepSeek API
