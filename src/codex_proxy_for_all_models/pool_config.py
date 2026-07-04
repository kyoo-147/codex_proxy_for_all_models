from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


REQUIRED_CURATED_PROFILES = ("codex-fast", "codex-balanced", "codex-strong")


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


@dataclass(slots=True)
class PoolDefinition:
    candidates: list[CandidateConfig] = field(default_factory=list)


@dataclass(slots=True)
class ProfileConfig:
    visible_slug: str
    display_name: str
    pool_order: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PoolConfig:
    mode: str
    profiles: dict[str, ProfileConfig]
    providers: dict[str, ProviderConfig]
    pools: dict[str, PoolDefinition]

    def visible_slugs(self) -> list[str]:
        return [profile.visible_slug for profile in self.profiles.values()]

    def default_visible_slug(self) -> str:
        if "codex-balanced" in self.profiles:
            return self.profiles["codex-balanced"].visible_slug
        visible = self.visible_slugs()
        return visible[0] if visible else "codex-balanced"


def load_pool_config(env: Mapping[str, str]) -> PoolConfig | None:
    path = env.get("CODEX_PROXY_CONFIG_PATH", "").strip()
    if not path:
        return None
    data = _load_toml(Path(path))
    return _parse_pool_config(data, env)


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            loaded = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"Pool config not found: {path}") from exc
    except (tomllib.TOMLDecodeError, OSError) as exc:
        raise ValueError(f"Invalid pool config: {path}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("Invalid pool config: root must be table")
    return loaded


def _parse_pool_config(data: Mapping[str, Any], env: Mapping[str, str]) -> PoolConfig:
    mode = _require_text(data, "mode", default="pool")
    profiles = _parse_profiles(data.get("profiles", {}))
    pools = _parse_pools(data.get("pools", {}))
    providers = _parse_providers(data.get("providers", {}), pools, env)
    _validate_curated_profiles(profiles)
    _validate_profile_pool_order(profiles, pools)
    _validate_candidate_providers(pools, providers)
    return PoolConfig(mode=mode, profiles=profiles, providers=providers, pools=pools)


def _parse_profiles(raw: Any) -> dict[str, ProfileConfig]:
    if raw in ({}, None):
        raise ValueError("Pool config missing profiles")
    if not isinstance(raw, dict):
        raise ValueError("Invalid pool config: profiles must be table")
    profiles: dict[str, ProfileConfig] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"Invalid profile: {name}")
        profiles[name] = ProfileConfig(
            visible_slug=_require_text(item, "visible_slug"),
            display_name=_require_text(item, "display_name"),
            pool_order=_require_text_list(item, "pool_order"),
        )
    if not profiles:
        raise ValueError("Pool config missing profiles")
    return profiles


def _parse_pools(raw: Any) -> dict[str, PoolDefinition]:
    if raw in ({}, None):
        raise ValueError("Pool config missing pools")
    if not isinstance(raw, dict):
        raise ValueError("Invalid pool config: pools must be table")
    pools: dict[str, PoolDefinition] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"Invalid pool: {name}")
        candidates_raw = item.get("candidates", [])
        if not isinstance(candidates_raw, list):
            raise ValueError(f"Invalid pool: {name}")
        candidates: list[CandidateConfig] = []
        for candidate_raw in candidates_raw:
            if not isinstance(candidate_raw, dict):
                raise ValueError(f"Invalid candidate in pool: {name}")
            candidates.append(
                CandidateConfig(
                    provider=_require_text(candidate_raw, "provider"),
                    model=_require_text(candidate_raw, "model"),
                    api_key_env=_require_text(candidate_raw, "api_key_env"),
                    capabilities=_require_text_list(candidate_raw, "capabilities"),
                )
            )
        pools[name] = PoolDefinition(candidates=candidates)
    if not pools:
        raise ValueError("Pool config missing pools")
    return pools


def _parse_providers(
    raw: Any,
    pools: Mapping[str, PoolDefinition],
    env: Mapping[str, str],
) -> dict[str, ProviderConfig]:
    if raw in ({}, None):
        raise ValueError("Pool config missing providers")
    if not isinstance(raw, dict):
        raise ValueError("Invalid pool config: providers must be table")

    provider_api_keys: dict[str, str] = {}
    for pool in pools.values():
        for candidate in pool.candidates:
            provider_api_keys.setdefault(candidate.provider, candidate.api_key_env)

    providers: dict[str, ProviderConfig] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"Invalid provider: {name}")
        api_key_env = _require_text(item, "api_key_env", default=provider_api_keys.get(name, ""))
        api_key = env.get(api_key_env, "").strip()
        if not api_key:
            raise ValueError(f"Missing env var: {api_key_env}")
        providers[name] = ProviderConfig(
            name=name,
            base_url=_require_text(item, "base_url"),
            provider_label=_require_text(item, "provider_label", default=name),
            api_key_env=api_key_env,
            api_key=api_key,
        )
    if not providers:
        raise ValueError("Pool config missing providers")
    return providers


def _validate_curated_profiles(profiles: Mapping[str, ProfileConfig]) -> None:
    missing = [name for name in REQUIRED_CURATED_PROFILES if name not in profiles]
    if missing:
        raise ValueError(f"Missing curated profiles: {', '.join(missing)}")


def _validate_profile_pool_order(
    profiles: Mapping[str, ProfileConfig],
    pools: Mapping[str, PoolDefinition],
) -> None:
    for profile_name, profile in profiles.items():
        if not profile.pool_order:
            raise ValueError(f"Profile '{profile_name}' missing pool_order")
        for pool_name in profile.pool_order:
            if pool_name not in pools:
                raise ValueError(
                    f"Profile '{profile_name}' references unknown pool '{pool_name}'"
                )


def _validate_candidate_providers(
    pools: Mapping[str, PoolDefinition],
    providers: Mapping[str, ProviderConfig],
) -> None:
    for pool_name, pool in pools.items():
        if not pool.candidates:
            raise ValueError(f"Pool '{pool_name}' has no candidates")
        for candidate in pool.candidates:
            if candidate.provider not in providers:
                raise ValueError(
                    f"Unknown provider '{candidate.provider}' in pool '{pool_name}'"
                )


def _require_text(raw: Mapping[str, Any], key: str, default: str = "") -> str:
    value = raw.get(key, default)
    text = str(value).strip() if value is not None else ""
    if not text:
        raise ValueError(f"Missing pool config field: {key}")
    return text


def _require_text_list(raw: Mapping[str, Any], key: str) -> list[str]:
    value = raw.get(key, [])
    if value in (None, ""):
        raise ValueError(f"Missing pool config field: {key}")
    if not isinstance(value, list):
        raise ValueError(f"Invalid pool config field: {key}")
    items = [str(item).strip() for item in value if str(item).strip()]
    if not items:
        raise ValueError(f"Missing pool config field: {key}")
    return items
