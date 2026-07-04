# Dev.to / Medium / Facebook Launch Post

**Title**: Codex Pool Router — free NVIDIA models with automatic failover

**Tone**: Codex-first, lightweight, practical, simpler than generic routers.

---

**Body draft**:

Codex works great with the Responses API, but most model providers only support chat/completions. The existing codex-proxy-for-all-models bridge handles that. The new v0.2 adds something Codex users have been asking for: curated model profiles with automatic failover.

Three clean profiles: Codex Fast, Codex Balanced, Codex Strong. Each routes through an NVIDIA-first pool with multi-key rotation and cooldown. Free tier hits a rate limit? Router swaps to the next candidate automatically. No model switching visible in Codex.

Still zero runtime dependencies. Still pure Python stdlib. Still one process.

Full details and setup guide on GitHub.
