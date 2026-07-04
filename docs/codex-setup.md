# Codex Setup

Point Codex app or Codex CLI at the proxy for single upstream or pool mode.

## Single upstream mode

Add to `~/.codex/config.toml`:

```toml
model = "z-ai/glm-5.2"
model_provider = "local_model_proxy"

[model_providers.local_model_proxy]
name = "Local Model Proxy"
base_url = "http://127.0.0.1:8787"
wire_api = "responses"
env_key = "DUMMY_API_KEY"
```

Set placeholder:

```bash
export DUMMY_API_KEY=dummy
```

## Pool mode

With pool mode, Codex sees three curated profiles: `Codex Fast`, `Codex Balanced`, `Codex Strong`.

Point Codex at the proxy as above. Select any of the three curated models from the Codex model dropdown.

The router handles failover, cooldown, and key rotation under the hood.

## Verify

```bash
curl http://127.0.0.1:8787/v1/models
```

Pool mode returns the three curated Codex profiles. Single upstream returns your configured model.
