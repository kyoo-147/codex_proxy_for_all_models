# v0.2 — Codex Pool Router

## What changed

- **Curated Codex profiles**: Codex Fast, Codex Balanced, Codex Strong — three clean options in the Codex model dropdown
- **NVIDIA-first pool routing**: multi-key failover, cooldown, and fallback across NVIDIA free and paid endpoints
- **Reasoning-aware routing**: low/medium/high effort maps to appropriate pool tiers
- **Sticky winners**: successful candidates stay active for 30s to reduce model switching
- **Cooldown windows**: rate limit (90s), server error (45s), timeout (30s), auth/not-found (disabled)
- **Single-process**: all routing state stays in memory — no database, no extra infra
- **Codex-first docs**: setup guides, NVIDIA pool guides, troubleshooting

## Setup

See [codex-setup.md](./codex-setup.md) and the example `config-examples/codex-pool.toml`.
