# Provider Compatibility

Results from real-world testing with Codex CLI through the proxy.

## Legend

| Icon | Meaning |
|---|---|
| ✅ | Good — works reliably in daily use |
| ⚠️ | Partial — works with caveats |
| ❌ | Broken — known issues, avoid |
| ? | Untested — not yet validated |

## Table

| Provider | Model | Tool calling | Context window | Rate limits | Streaming | Notes |
|---|---|---|---|---|---|---|
| **Ollama** | qwen3:8b | ✅ | ⚠️ | ✅ | ⚠️ | Tool calling works well; small context (~8K) may truncate long sessions |
| **Ollama** | llama3.1:8b | ✅ | ⚠️ | ✅ | ⚠️ | Good tool support; similar context limits |
| **Ollama** | glm4:9b | ⚠️ | ⚠️ | ✅ | ⚠️ | Some tool-call quirks; test before long sessions |
| **NVIDIA Build** | z-ai/glm-5.2 | ✅ | ✅ | ⚠️ | ✅ | Reliable; rate limits can hit on heavy usage |
| **NVIDIA Build** | qwen/qwen3-next-80b | ✅ | ✅ | ⚠️ | ✅ | Good for complex tasks; generous context |
| **NVIDIA Build** | deepseek-ai/deepseek-v4-* | ✅ | ✅ | ⚠️ | ✅ | Strong reasoning; rate limits apply |
| **OpenRouter** | varies | ✅ | ✅ | ⚠️ | ✅ | Quality depends on upstream model; most work well |
| **vLLM** | Qwen/Qwen3-32B | ✅ | ✅ | ✅ | ✅ | Reliable for self-hosted deployments |
| **SGLang** | deepseek-ai/DeepSeek-V3 | ⚠️ | ✅ | ✅ | ⚠️ | Tool calling varies by backend version |
| **LM Studio** | local models | ⚠️ | ⚠️ | ✅ | ⚠️ | Depends on loaded model; test tool calls per session |

## Notes

- All providers above expose `POST /v1/chat/completions` with bearer-token auth.
- Tool-calling quality depends on the upstream model's native function-calling support, not the proxy.
- Streaming is **not** supported by the proxy — all requests are blocking.
- Context window limits are imposed by the upstream; the proxy passes them through.
- For rate-limited providers, pool mode with failover candidates can reduce disruption.

## Adding a new provider

1. Test basic text round-trip: `POST /v1/responses` with `{"input": "hello"}`
2. Test tool-calling: `POST /v1/responses` with a `function_call` + `function_call_output` input
3. Run the validation script: `scripts/validate-provider.sh` (or `.bat`)
4. Open a PR or issue with your results to update this table.
