# Codex Pool Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Codex-first lightweight pool router that exposes `Codex Fast`, `Codex Balanced`, and `Codex Strong`, routes to NVIDIA-first model pools with multi-key failover, and ships the docs/assets needed for a professional v0.2 release.

**Architecture:** Keep the existing single-process HTTP proxy, but split selection logic into focused modules for config loading, curated catalog generation, provider calls, and in-memory routing state. Preserve single-upstream mode while adding optional `TOML + env` pool mode, then layer Codex-facing docs, Open Graph assets, and release collateral on top.

**Tech Stack:** Python standard library (`dataclasses`, `tomllib`/compat parser, `urllib`, `http.server`, `time`, `threading`), `unittest`, Pillow for generated repo media, GitHub release/docs assets.

## Global Constraints

- Keep product positioning Codex-first, not a generic orchestration platform.
- Keep implementation single-process and lightweight.
- Preserve simple existing single-upstream mode.
- Use `TOML + env` for pool mode.
- Prefer NVIDIA-first with optional cross-vendor fallback.
- Expose exactly three curated Codex models: `Codex Fast`, `Codex Balanced`, `Codex Strong`.
- Keep runtime state in memory only.
- Keep setup easy for Codex users on Windows, macOS, and Linux.
- Avoid hardcoding unstable claims like an exact count of free NVIDIA models.
- Keep user-facing errors short and actionable.

---

### Task 1: Add Pool Config Loader And Typed Router Settings

**Files:**
- Create: `src/codex_proxy_for_all_models/pool_config.py`
- Modify: `src/codex_proxy_for_all_models/config.py`
- Modify: `src/codex_proxy_for_all_models/cli.py`
- Modify: `config-examples/codex.config.toml`
- Create: `config-examples/codex-pool.toml`
- Test: `tests/test_pool_config.py`

**Interfaces:**
- Consumes: `load_config(env: Mapping[str, str]) -> ProxyConfig`
- Produces: `load_pool_config(env: Mapping[str, str]) -> PoolConfig | None`
- Produces: `PoolConfig.profiles: dict[str, ProfileConfig]`
- Produces: `ProfileConfig.visible_slug: str`
- Produces: `CandidateConfig.api_key_env: str`

- [ ] **Step 1: Write the failing config tests**

```python
import os
import tempfile
import unittest

from codex_proxy_for_all_models.pool_config import load_pool_config


class PoolConfigTests(unittest.TestCase):
    def test_loads_profiles_and_candidates_from_toml_and_env(self):
        toml_text = """
mode = "pool"

[profiles.codex_balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free", "coding_fast"]

[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"

[[pools.cheap_free.candidates]]
provider = "nvidia_free"
model = "z-ai/glm-5.2"
api_key_env = "NVIDIA_FREE_KEY"
capabilities = ["free", "tool_call"]
"""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".toml") as handle:
            handle.write(toml_text)
            path = handle.name
        env = {
            "CODEX_PROXY_CONFIG_PATH": path,
            "NVIDIA_FREE_KEY": "token-1",
        }

        config = load_pool_config(env)

        self.assertEqual(config.mode, "pool")
        self.assertIn("codex_balanced", config.profiles)
        self.assertEqual(config.providers["nvidia_free"].api_key, "token-1")
        self.assertEqual(config.pools["cheap_free"].candidates[0].model, "z-ai/glm-5.2")

    def test_returns_none_when_no_pool_config_path_is_set(self):
        self.assertIsNone(load_pool_config({}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_pool_config -v`
Expected: FAIL with `ModuleNotFoundError` or `cannot import name 'load_pool_config'`

- [ ] **Step 3: Write minimal pool config implementation**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


@dataclass(slots=True)
class ProviderConfig:
    name: str
    base_url: str
    provider_label: str
    api_key_env: str
    api_key: str


@dataclass(slots=True)
class CandidateConfig:
    provider: str
    model: str
    api_key_env: str
    capabilities: list[str] = field(default_factory=list)


def load_pool_config(env: dict[str, str]) -> "PoolConfig | None":
    path = env.get("CODEX_PROXY_CONFIG_PATH", "").strip()
    if not path:
        return None
    data = _load_toml(Path(path))
    return PoolConfig.from_data(data, env)
```

- [ ] **Step 4: Extend existing config entrypoint to carry optional pool mode**

```python
from .pool_config import load_pool_config


@dataclass(slots=True)
class ProxyConfig:
    upstream_base_url: str
    upstream_api_key: str
    upstream_model: str
    provider_label: str = "OpenAI-Compatible"
    pool_config: "PoolConfig | None" = None


def load_config(env: Mapping[str, str]) -> ProxyConfig:
    pool_config = load_pool_config(dict(env))
    if pool_config is not None:
        return ProxyConfig(
            upstream_base_url="",
            upstream_api_key="",
            upstream_model="codex-balanced",
            provider_label="Codex Pool Router",
            pool_config=pool_config,
        )
```

- [ ] **Step 5: Update CLI startup messaging for pool mode**

```python
if config.pool_config is not None:
    print("[proxy] mode=pool")
    print(f"[proxy] profiles={', '.join(config.pool_config.visible_slugs())}")
else:
    print("[proxy] mode=single-upstream")
```

- [ ] **Step 6: Run config tests and existing suite**

Run: `python -m unittest tests.test_pool_config tests.test_config -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/codex_proxy_for_all_models/pool_config.py src/codex_proxy_for_all_models/config.py src/codex_proxy_for_all_models/cli.py config-examples/codex.config.toml config-examples/codex-pool.toml tests/test_pool_config.py
git commit -m "feat: add pool config loader"
```

### Task 2: Expose Curated Codex Models In Catalog And Parse Routing Intent

**Files:**
- Create: `src/codex_proxy_for_all_models/catalog.py`
- Modify: `src/codex_proxy_for_all_models/protocol.py`
- Modify: `src/codex_proxy_for_all_models/server.py`
- Test: `tests/test_catalog.py`
- Modify: `tests/test_protocol.py`

**Interfaces:**
- Consumes: `PoolConfig.profiles`
- Produces: `build_model_catalog(config: ProxyConfig) -> dict`
- Produces: `extract_reasoning_effort(request: dict) -> str`
- Produces: `resolve_requested_profile(requested_model: str | None, config: ProxyConfig) -> str`

- [ ] **Step 1: Write failing catalog tests**

```python
import unittest

from codex_proxy_for_all_models.catalog import build_model_catalog
from codex_proxy_for_all_models.pool_config import PoolConfig, ProfileConfig


class CatalogTests(unittest.TestCase):
    def test_pool_mode_exposes_three_curated_models(self):
        config = PoolConfig(
            mode="pool",
            profiles={
                "codex_fast": ProfileConfig(visible_slug="codex-fast", display_name="Codex Fast", pool_order=["coding_fast"]),
                "codex_balanced": ProfileConfig(visible_slug="codex-balanced", display_name="Codex Balanced", pool_order=["cheap_free"]),
                "codex_strong": ProfileConfig(visible_slug="codex-strong", display_name="Codex Strong", pool_order=["coding_strong"]),
            },
            pools={},
            providers={},
        )

        payload = build_model_catalog(config)
        names = [item["display_name"] for item in payload["models"]]

        self.assertEqual(names, ["Codex Fast", "Codex Balanced", "Codex Strong"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_catalog -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'codex_proxy_for_all_models.catalog'`

- [ ] **Step 3: Implement curated catalog builder**

```python
def build_model_catalog(config: ProxyConfig) -> dict:
    if config.pool_config is None:
        return model_catalog_payload(
            model_slug=config.upstream_model,
            display_name=config.upstream_model,
            provider_label=config.provider_label,
            context_window=config.context_window,
            max_output_tokens=config.max_output_tokens,
        )

    models = []
    for profile in config.pool_config.ordered_profiles():
        models.append(
            curated_model_entry(
                slug=profile.visible_slug,
                display_name=profile.display_name,
                description=profile.description,
            )
        )
    return {"object": "list", "models": models}
```

- [ ] **Step 4: Add protocol helper for reasoning extraction**

```python
def extract_reasoning_effort(request: dict) -> str:
    reasoning = request.get("reasoning", {}) or {}
    effort = str(reasoning.get("effort", "medium")).strip().lower()
    if effort not in {"low", "medium", "high"}:
        return "medium"
    return effort
```

- [ ] **Step 5: Update server model catalog endpoint to use curated catalog**

```python
if path in {"/models", "/v1/models"}:
    self._json(200, build_model_catalog(config))
    return
```

- [ ] **Step 6: Run focused tests**

Run: `python -m unittest tests.test_catalog tests.test_protocol -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/codex_proxy_for_all_models/catalog.py src/codex_proxy_for_all_models/protocol.py src/codex_proxy_for_all_models/server.py tests/test_catalog.py tests/test_protocol.py
git commit -m "feat: add curated Codex model catalog"
```

### Task 3: Add In-Memory Router With Tier Selection, Cooldown, And Sticky Winner

**Files:**
- Create: `src/codex_proxy_for_all_models/router.py`
- Modify: `src/codex_proxy_for_all_models/pool_config.py`
- Test: `tests/test_router.py`

**Interfaces:**
- Consumes: `PoolConfig`, `ProfileConfig`, `PoolDefinition`, `CandidateConfig`
- Produces: `PoolRouter.select_candidate(profile_slug: str, reasoning_effort: str) -> RoutedCandidate`
- Produces: `PoolRouter.report_success(candidate_id: str) -> None`
- Produces: `PoolRouter.report_failure(candidate_id: str, failure: FailureKind) -> None`
- Produces: `FailureKind = Literal["rate_limit", "server_error", "timeout", "auth", "not_found"]`

- [ ] **Step 1: Write failing router tests**

```python
import unittest

from codex_proxy_for_all_models.router import PoolRouter


class RouterTests(unittest.TestCase):
    def test_selects_first_healthy_candidate_for_balanced_profile(self):
        router = build_router_fixture()

        candidate = router.select_candidate("codex-balanced", "medium")

        self.assertEqual(candidate.model, "z-ai/glm-5.2")

    def test_rate_limit_moves_candidate_into_cooldown_and_chooses_next(self):
        router = build_router_fixture()
        first = router.select_candidate("codex-balanced", "medium")
        router.report_failure(first.candidate_id, "rate_limit")

        second = router.select_candidate("codex-balanced", "medium")

        self.assertNotEqual(first.candidate_id, second.candidate_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_router -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'codex_proxy_for_all_models.router'`

- [ ] **Step 3: Implement router state and failure classification**

```python
from dataclasses import dataclass
import time


@dataclass(slots=True)
class RoutedCandidate:
    candidate_id: str
    provider_name: str
    model: str
    api_key: str
    base_url: str


class PoolRouter:
    def __init__(self, config: PoolConfig, clock: callable | None = None) -> None:
        self._config = config
        self._clock = clock or time.time
        self._cooldowns: dict[str, float] = {}
        self._sticky_winners: dict[str, tuple[str, float]] = {}
```

- [ ] **Step 4: Implement profile-to-tier selection and sticky reuse**

```python
def select_candidate(self, profile_slug: str, reasoning_effort: str) -> RoutedCandidate:
    profile = self._config.profile_by_slug(profile_slug)
    pool_names = profile.resolve_pool_order(reasoning_effort)
    sticky = self._sticky_winners.get(profile_slug)
    if sticky and sticky[1] > self._clock():
        candidate = self._config.candidate_by_id(sticky[0])
        if not self._is_in_cooldown(candidate.candidate_id):
            return self._to_routed_candidate(candidate)
    for pool_name in pool_names:
        for candidate in self._config.pools[pool_name].ordered_candidates():
            if not self._is_in_cooldown(candidate.candidate_id):
                return self._to_routed_candidate(candidate)
    raise RuntimeError(f"All candidates unavailable for profile {profile_slug}")
```

- [ ] **Step 5: Implement failure reporting with cooldown windows**

```python
def report_failure(self, candidate_id: str, failure: str) -> None:
    now = self._clock()
    delay = {
        "rate_limit": 90,
        "server_error": 45,
        "timeout": 30,
        "auth": 3600,
        "not_found": 3600,
    }[failure]
    self._cooldowns[candidate_id] = now + delay
```

- [ ] **Step 6: Run router tests**

Run: `python -m unittest tests.test_router -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/codex_proxy_for_all_models/router.py src/codex_proxy_for_all_models/pool_config.py tests/test_router.py
git commit -m "feat: add in-memory pool router"
```

### Task 4: Wire Router Into Upstream Calls And Preserve Single-Upstream Compatibility

**Files:**
- Create: `src/codex_proxy_for_all_models/providers.py`
- Modify: `src/codex_proxy_for_all_models/server.py`
- Modify: `src/codex_proxy_for_all_models/protocol.py`
- Modify: `src/codex_proxy_for_all_models/cli.py`
- Modify: `tests/test_server.py`
- Create: `tests/test_providers.py`

**Interfaces:**
- Consumes: `PoolRouter.select_candidate(...) -> RoutedCandidate`
- Produces: `call_upstream(config: ProxyConfig, payload: dict, requested_model: str | None, reasoning_effort: str) -> dict`
- Produces: `classify_upstream_failure(exc: Exception) -> FailureKind`

- [ ] **Step 1: Write failing provider failover tests**

```python
import unittest

from codex_proxy_for_all_models.providers import classify_upstream_failure


class ProviderTests(unittest.TestCase):
    def test_classifies_429_as_rate_limit(self):
        error = RuntimeError("Upstream 429: too many requests")
        self.assertEqual(classify_upstream_failure(error), "rate_limit")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_providers -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'codex_proxy_for_all_models.providers'`

- [ ] **Step 3: Move HTTP request code into provider helper**

```python
def _post_chat_completion(base_url: str, api_key: str, extra_headers: dict[str, str], payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "codex-proxy-for-all-models/0.2",
    }
    headers.update(extra_headers)
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
```

- [ ] **Step 4: Add pool-aware upstream call wrapper**

```python
def call_upstream(config: ProxyConfig, payload: dict, requested_model: str | None, reasoning_effort: str) -> dict:
    if config.pool_config is None:
        payload["model"] = config.upstream_model
        return _post_chat_completion(config.upstream_base_url, config.upstream_api_key, config.extra_headers or {}, payload)

    profile_slug = resolve_requested_profile(requested_model, config)
    attempts = []
    for _ in range(config.pool_config.max_attempts):
        candidate = config.pool_router.select_candidate(profile_slug, reasoning_effort)
        payload["model"] = candidate.model
        try:
            response = _post_chat_completion(candidate.base_url, candidate.api_key, config.extra_headers or {}, payload)
            config.pool_router.report_success(candidate.candidate_id)
            return response
        except Exception as exc:
            failure = classify_upstream_failure(exc)
            config.pool_router.report_failure(candidate.candidate_id, failure)
            attempts.append(f"{candidate.model}:{failure}")
    raise RuntimeError(f"Pool request failed for {profile_slug}; attempts={', '.join(attempts)}")
```

- [ ] **Step 5: Update `/responses` and `/chat/completions` handlers to pass reasoning and requested model**

```python
request = json.loads(raw.decode("utf-8"))
reasoning_effort = extract_reasoning_effort(request)
requested_model = request.get("model")
upstream_request = responses_to_chat_request(request, requested_model or config.upstream_model)
upstream_response = call_upstream(config, upstream_request, requested_model, reasoning_effort)
```

- [ ] **Step 6: Run full server and provider tests**

Run: `python -m unittest tests.test_providers tests.test_server -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/codex_proxy_for_all_models/providers.py src/codex_proxy_for_all_models/server.py src/codex_proxy_for_all_models/protocol.py src/codex_proxy_for_all_models/cli.py tests/test_providers.py tests/test_server.py
git commit -m "feat: wire pool router into upstream calls"
```

### Task 5: Ship Codex-First Docs, Social Preview, PyPI Badge Path, And Launch Content

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Modify: `scripts/generate_readme_media.py`
- Create: `assets/social-preview-github.png`
- Create: `assets/social-preview-og.png`
- Create: `docs/codex-setup.md`
- Create: `docs/nvidia-pools.md`
- Create: `docs/publishing.md`
- Create: `docs/release-notes-v0.2.md`
- Create: `docs/devto-medium-facebook-launch.md`

**Interfaces:**
- Consumes: curated profile names, NVIDIA-first messaging, pool-mode config example
- Produces: repo docs and assets only

- [ ] **Step 1: Write a lightweight verification checklist file for docs deliverables**

```markdown
# v0.2 Content Checklist

- README mentions Codex Fast, Codex Balanced, Codex Strong
- README includes PyPI badge placeholder
- docs/codex-setup.md explains `~/.codex/config.toml`
- docs/nvidia-pools.md explains free and paid NVIDIA key flows
- docs/publishing.md includes `python -m build`
```

- [ ] **Step 2: Add social preview generation support**

```python
def draw_social_preview(output_path: Path, title: str, subtitle: str) -> None:
    image = gradient_background((1280, 640))
    draw = ImageDraw.Draw(image)
    rounded_panel(draw, (64, 64, 1216, 576), "#0d1529", "#24324f")
    draw.text((112, 128), title, font=TITLE_FONT, fill="#f4f7fb")
    draw.text((112, 226), subtitle, font=SUBTITLE_FONT, fill="#b8c4d9", spacing=8)
    image.save(output_path, optimize=True)
```

- [ ] **Step 3: Update README positioning and badge block**

```markdown
[![PyPI](https://img.shields.io/pypi/v/codex-proxy-for-all-models.svg)](https://pypi.org/project/codex-proxy-for-all-models/)

Codex-first lightweight model bridge for NVIDIA NIM and other OpenAI-compatible backends.

Visible profiles inside Codex:

- `Codex Fast`
- `Codex Balanced`
- `Codex Strong`
```

- [ ] **Step 4: Add publishing and NVIDIA pool docs**

```markdown
## Publish to PyPI

```bash
python -m build
python -m twine upload dist/*
```

## NVIDIA pool presets

- free-only pool
- free + paid fallback pool
- cross-vendor emergency fallback
```

- [ ] **Step 5: Add long-form release notes and social post drafts**

```markdown
## What changed in v0.2

- Added curated Codex routing profiles
- Added NVIDIA-first pool routing with multi-key failover
- Preserved lightweight single-process architecture
- Added Codex-first setup docs and social preview assets
```

- [ ] **Step 6: Regenerate media and run full test suite**

Run: `python scripts/generate_readme_media.py`
Expected: `assets/hero.png`, `assets/demo.gif`, `assets/social-preview-github.png`, and `assets/social-preview-og.png` exist

Run: `python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add README.md CHANGELOG.md pyproject.toml scripts/generate_readme_media.py assets docs
git commit -m "docs: ship Codex-first router launch assets"
```

### Task 6: Final Verification And Release Prep

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/release-notes-v0.2.md`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: completed tasks 1-5
- Produces: release-ready repo with verified commands and CI coverage

- [ ] **Step 1: Add pool-mode tests to CI command**

```yaml
- name: Run tests
  run: python -m unittest discover -s tests -v
```

- [ ] **Step 2: Add v0.2 changelog entry**

```markdown
## 0.2.0

- Added Codex Fast, Codex Balanced, and Codex Strong profiles
- Added NVIDIA-first pool routing with cooldown and failover
- Added Codex-first setup docs, social preview assets, and PyPI publish guidance
```

- [ ] **Step 3: Run end-to-end verification commands**

Run: `python -m unittest discover -s tests -v`
Expected: PASS

Run: `python codex_proxy_for_all_models.py`
Expected: startup log shows either `mode=single-upstream` or `mode=pool`

Run: `git status --short`
Expected: empty output

- [ ] **Step 4: Prepare release commit**

```bash
git add .github/workflows/ci.yml CHANGELOG.md docs/release-notes-v0.2.md
git commit -m "chore: prepare v0.2 release"
```

- [ ] **Step 5: Tag release candidate**

```bash
git tag -a v0.2.0 -m "v0.2.0"
git push origin main --tags
```

- [ ] **Step 6: Publish release notes**

```text
Use docs/release-notes-v0.2.md as GitHub release body.
Use docs/devto-medium-facebook-launch.md for launch posts.
```

- [ ] **Step 7: Commit any final metadata changes**

```bash
git add README.md docs assets
git commit -m "chore: finalize v0.2 metadata"
```
