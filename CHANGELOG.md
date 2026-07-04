# Changelog

## 0.2.0

- Added Codex Fast, Codex Balanced, and Codex Strong curated profiles
- Added NVIDIA-first pool routing with multi-key failover and cooldown
- Added reasoning-aware routing (low/medium/high effort → pool tier)
- Added sticky winners (30s window) for consistent candidate reuse
- Added TOML + env pool configuration
- Added Codex-first setup docs, NVIDIA pool guides, and PyPI publish guidance
- Added social preview and Open Graph assets
- Added pool config example and release notes
- Preserved single-upstream mode compatibility

## 0.1.0

- Rebuilt the project as a vendor-agnostic Codex proxy
- Added stdlib package layout under `src/`
- Added integration tests
- Added provider docs and config examples
- Added cross-platform helper scripts
