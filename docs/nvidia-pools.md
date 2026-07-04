# NVIDIA Pool Setups

## Free-only pool

Set `NVIDIA_FREE_KEY` to any NVIDIA Build API key. The pool uses free-tier endpoints.

```toml
[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_FREE_KEY"
```

## Free + paid fallback

Add a paid key for overflow when free-tier rate limits hit.

```toml
[providers.nvidia_paid]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_PAID_KEY"
```

## Cross-vendor fallback

For resilient setups, add OpenRouter or other OpenAI-compatible vendor.

```toml
[providers.openrouter]
base_url = "https://openrouter.ai/api/v1"
provider_label = "OpenRouter"
api_key_env = "OPENROUTER_KEY"
```
