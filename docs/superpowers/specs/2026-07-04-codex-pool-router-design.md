# Codex Pool Router Design

Date: 2026-07-04
Repo: `kyoo-147/codex_proxy_for_all_models`
Status: Draft approved in chat, written for review before implementation planning

## Goal

Evolve `codex_proxy_for_all_models` from a single-upstream Codex bridge into a Codex-first pool router that stays lightweight, easy to install, and stable under free-tier or rate-limited upstream conditions.

This product is not trying to become a generic mega-router. It should stay focused on:

- Codex app users
- Codex CLI users
- OpenAI-compatible `chat/completions` backends
- NVIDIA NIM / NVIDIA Build as primary upstream family
- simple local setup with minimal moving parts

## Product Positioning

Core message:

`Codex-first lightweight model bridge for NVIDIA NIM and other OpenAI-compatible backends.`

Product promises:

- Keep Codex UX intact
- Hide backend complexity behind curated Codex-friendly profiles
- Prefer lightweight implementation over "smart router" complexity
- Make free NVIDIA models practical for real daily coding use
- Support paid NVIDIA keys and cross-vendor fallback without vendor lock-in

This repo should market itself to Codex users first, not to users looking for a generic multi-provider orchestration platform.

## Target Users

Primary users:

- People who like Codex desktop app UX
- People using Codex CLI for coding work
- People wanting cheaper or free backends through Codex
- People wanting fallback when a free or busy model gets rate-limited

Secondary users:

- Power users who want custom model pools
- Teams who want NVIDIA-first routing with optional fallback vendors

## Scope

In scope for next phase:

- Tier/profile router for Codex
- NVIDIA-first multi-model failover
- multi-API-key rotation
- cooldown and retry logic
- curated Codex-visible model catalog
- `TOML + env` configuration
- social preview / Open Graph assets
- PyPI-ready README badge and packaging polish
- long-form release notes for social and blog posting
- Codex-focused setup/docs/skills guidance

Out of scope for next phase:

- database-backed routing state
- advanced telemetry backend
- prompt classification ML
- generic multi-tenant gateway behavior
- streaming-specific optimization beyond current baseline

## UX Model In Codex

The Codex app should expose only a small curated model list:

- `Codex Fast`
- `Codex Balanced`
- `Codex Strong`

These are not raw upstream models. They are router profiles.

Benefits:

- keeps Codex dropdown simple
- aligns with how Codex users think about coding work
- allows backend changes without user reconfiguration
- preserves room for provider/model fallback under the hood

## Routing Strategy

### Provider strategy

Default stance:

- NVIDIA-first
- cross-vendor fallback second

This means:

- primary candidates should come from NVIDIA free or paid endpoints
- if a full tier becomes unhealthy or exhausted, router may fall back to optional secondary providers such as Ollama, OpenRouter, or vLLM

### Profile strategy

Visible curated profiles:

- `Codex Fast`
- `Codex Balanced`
- `Codex Strong`

Internal mapping goals:

- `Codex Fast`: low-latency coding/help tasks
- `Codex Balanced`: default daily Codex work, free-first and resilient
- `Codex Strong`: harder multi-file, tool-heavy, longer reasoning sessions

### Reasoning-aware mapping

Proxy should read Codex reasoning level and map it to internal tier intent:

- `low -> coding-fast`
- `medium -> cheap-free`
- `high -> coding-strong`

Curated profile selected by user remains primary. Reasoning level is then used as a sub-signal inside that profile to choose the best candidate pool path.

## Pool Architecture

Router should remain single-process, but split into a focused pool engine module.

Recommended modules:

- `config.py`: load and validate config
- `router.py`: profile selection, candidate ordering, cooldown, retry, failover
- `providers.py`: upstream request preparation and provider-specific behavior
- `catalog.py`: Codex model catalog payload generation
- `server.py`: thin HTTP layer

Optional supporting files:

- `profiles/default.toml`
- `profiles/nvidia-first.toml`
- `config-examples/codex-proxy.toml`

## Configuration Model

Configuration style:

- `TOML` for pool definitions and profile structure
- environment variables for secrets

Example split:

- `codex-proxy.toml`
  - profiles
  - tiers
  - candidate lists
  - provider refs
  - cooldown/retry numbers
- env vars
  - NVIDIA free key
  - NVIDIA paid key
  - OpenRouter key
  - any other provider secrets

Why this shape:

- readable and reviewable
- easier for Codex users than giant JSON env blobs
- avoids hardcoding secrets
- still simple to distribute in repo examples

## Candidate Model

Each candidate should support fields like:

- `provider`
- `model`
- `api_key_env`
- `weight`
- `capabilities`
- `cooldown_until`
- `enabled`

Capabilities can include:

- `fast`
- `strong`
- `tool_call`
- `long_context`
- `free`
- `paid`

State should stay in memory for now.

## Failover And Cooldown Rules

Behavior goals:

- stable enough for real Codex sessions
- simple enough to reason about
- no extra infra

Request flow:

1. receive Codex request
2. identify curated profile
3. read reasoning level
4. choose internal pool order
5. pick first healthy candidate not in cooldown
6. call upstream
7. if success, mark candidate as short-term sticky winner
8. if failure, classify and fail over

Failure rules:

- `429`: rate-limit cooldown, then next candidate
- `5xx`: service cooldown, then next candidate
- timeout/network error: short/medium cooldown, then next candidate
- auth/key error: disable that key slot for current runtime
- deprecated/not-found model: disable candidate for current runtime

Cooldown defaults:

- `429`: 60-180 seconds
- `5xx`: 30-90 seconds
- timeout: 20-60 seconds
- auth failure: disabled until restart or config reload

Retry limits:

- try 2-4 candidates max per request
- fail fast enough to keep Codex responsive

Sticky winner:

- if a candidate succeeds, prefer it again for a short time window
- reduces unnecessary model switching
- improves perceived consistency for Codex users

Cross-tier fallback:

- `cheap-free` can fall forward to `coding-fast`
- `coding-fast` can fall forward to `coding-strong`
- `coding-strong` can fall back to a stable paid or secondary provider candidate if configured

## NVIDIA Model Strategy

NVIDIA is primary because official public pages currently advertise free inference and a wide model catalog:

- [NVIDIA Build home](https://build.nvidia.com/)
- [NVIDIA model catalog](https://build.nvidia.com/models)
- [NVIDIA chat completions docs](https://docs.api.nvidia.com/nim/reference/google-codegemma-7b-infer)

Product assumption:

- many NVIDIA models are usable through free endpoints
- free endpoint limits or temporary slowness will happen
- rotating across a preselected pool is practical

Implementation should not hardcode a claim like "exactly 77 free models" unless that count is confirmed from a stable official source at publish time.

Instead:

- document that NVIDIA offers many free endpoint models
- ship curated recommended lists for coding-friendly profiles
- allow users to edit pool membership easily

Need docs for:

- NVIDIA free-only setup
- NVIDIA paid-key setup
- mixed free + paid setup
- NVIDIA-first with cross-vendor fallback

## Codex-Specific Features

This repo should lean into Codex-specific behavior instead of generic routing features.

Examples:

- curated model catalog that looks natural inside Codex
- reasoning-level aware routing
- error messages phrased for Codex users
- setup docs that show `~/.codex/config.toml`
- examples for Codex desktop and Codex CLI
- troubleshooting around "Custom" provider display in Codex

## Skill Layer

"Skill" should be treated in two ways:

### 1. Capability profiles inside code

These are the curated routing personalities:

- `Codex Fast`
- `Codex Balanced`
- `Codex Strong`

### 2. Codex user guidance in repo

These are documentation/preset workflows that help Codex users succeed fast:

- recommended setup guides
- preset config files
- troubleshooting guides
- workflow examples by coding use case

Potential docs/skill ideas:

- "Best free Codex setup with NVIDIA"
- "Stable Codex setup with NVIDIA paid fallback"
- "When to use Fast vs Balanced vs Strong"
- "How Codex reasoning maps into router behavior"

## Social Preview And README

Repo should have dedicated social preview / Open Graph assets, not only README inline art.

Deliverables:

- GitHub social preview image sized for repo sharing
- optional Open Graph image variant for docs/blog use
- README hero and demo assets
- messaging aligned with Codex-first positioning

## PyPI Readiness

Repo should be ready for package publishing, even if publish step is optional.

Deliverables:

- README badge for PyPI once package exists
- docs for `python -m build` and `twine upload`
- packaging metadata tightened around Codex-first messaging
- release checklist covering PyPI publish

## Release Notes And Content

Need longer-form content beyond GitHub tag notes:

- GitHub release notes
- Dev.to article draft
- Medium article draft
- Facebook post draft

Tone:

- Codex-first
- lightweight
- practical
- NVIDIA-first but not locked in
- simpler than generic routers

## Testing Strategy

Need tests for:

- config parsing from `TOML + env`
- curated catalog payloads
- profile selection
- reasoning-aware internal routing
- rate-limit failover
- timeout failover
- disabled key handling
- sticky winner behavior
- cross-tier fallback

Integration tests should stay lightweight using fake local upstream servers.

## Error Handling

User-facing errors should prefer short, actionable messages.

Examples:

- upstream rate-limited, switched candidate
- all candidates in `Codex Balanced` unavailable
- missing API key env for configured provider
- configured model no longer available upstream

Avoid huge logs by default. Keep debug mode optional.

## Migration Strategy

Current repo already supports single-upstream mode. Migration path should be:

1. keep existing simple mode working
2. introduce optional pool config mode
3. ship NVIDIA-first preset
4. switch README/docs to emphasize curated Codex router mode

This avoids breaking current users who only want one upstream model.

## Recommended Implementation Order

1. add router/pool engine and `TOML + env` config
2. add curated Codex catalog models
3. add NVIDIA-first presets and docs
4. add retry/cooldown/fallback tests
5. add social preview assets and README polish
6. add PyPI badge/publish docs
7. add long-form release notes drafts

## Risks

- too much routing logic could bloat the repo
- overexposing raw model choices could hurt UX
- unstable external model availability may make docs stale
- unsupported upstream tool-call quirks may reduce consistency

Mitigations:

- keep three curated Codex models only
- keep in-memory state only
- document recommended models as editable presets, not hard promises
- keep vendor abstraction thin

## Success Criteria

This phase is successful when:

- Codex users can install proxy quickly
- Codex shows three curated model choices
- router survives common free-tier rate limits by failing over cleanly
- NVIDIA free and paid setups are both documented
- repo messaging clearly says Codex-first and lightweight
- package/release/social assets look professional

## Open Questions Resolved

Resolved in chat:

- architecture: single-process with dedicated pool engine
- provider stance: NVIDIA-first with cross-vendor fallback
- visible UX: three curated Codex models
- selection style: reasoning-aware routing
- config style: `TOML + env`
- skills concept: both code capability profiles and user-facing Codex guidance

## Recommendation

Proceed with a Codex-first v0.2 design that adds a lightweight router engine without turning the repo into a generic orchestration platform.

The north star is:

`Make Codex work reliably with NVIDIA free/paid pools and simple fallback, while keeping setup and mental overhead low.`
