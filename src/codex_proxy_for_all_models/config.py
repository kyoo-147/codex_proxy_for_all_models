from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

from .pool_config import PoolConfig, load_pool_config


@dataclass(slots=True)
class ProxyConfig:
    upstream_base_url: str
    upstream_api_key: str
    upstream_model: str
    provider_label: str = "OpenAI-Compatible"
    listen_host: str = "127.0.0.1"
    listen_port: int = 8787
    debug_log: str = ""
    extra_headers: dict[str, str] | None = None
    context_window: int = 262144
    max_output_tokens: int = 16384
    pool_config: PoolConfig | None = None

    def __post_init__(self) -> None:
        self.upstream_base_url = self.upstream_base_url.rstrip("/")
        if self.extra_headers is None:
            self.extra_headers = {}


def load_config(env: Mapping[str, str]) -> ProxyConfig:
    pool_config = load_pool_config(env)
    if pool_config is not None:
        return ProxyConfig(
            upstream_base_url="",
            upstream_api_key="",
            upstream_model=pool_config.default_visible_slug(),
            provider_label="Codex Pool Router",
            listen_host=env.get("CODEX_PROXY_LISTEN_HOST", "127.0.0.1").strip() or "127.0.0.1",
            listen_port=int(env.get("CODEX_PROXY_LISTEN_PORT", "8787")),
            debug_log=env.get("CODEX_PROXY_DEBUG_LOG", "").strip(),
            extra_headers=_parse_extra_headers(env),
            context_window=int(env.get("CODEX_PROXY_CONTEXT_WINDOW", "262144")),
            max_output_tokens=int(env.get("CODEX_PROXY_MAX_OUTPUT_TOKENS", "16384")),
            pool_config=pool_config,
        )

    base_url = env.get("CODEX_PROXY_UPSTREAM_BASE_URL", "").strip()
    api_key = env.get("CODEX_PROXY_UPSTREAM_API_KEY", "").strip()
    model = env.get("CODEX_PROXY_UPSTREAM_MODEL", "").strip()
    if not base_url or not api_key or not model:
        raise ValueError(
            "Missing required environment. Need CODEX_PROXY_UPSTREAM_BASE_URL, "
            "CODEX_PROXY_UPSTREAM_API_KEY, CODEX_PROXY_UPSTREAM_MODEL."
        )

    extra_headers_raw = env.get("CODEX_PROXY_EXTRA_HEADERS", "").strip()
    extra_headers = json.loads(extra_headers_raw) if extra_headers_raw else {}

    return ProxyConfig(
        upstream_base_url=base_url,
        upstream_api_key=api_key,
        upstream_model=model,
        provider_label=env.get("CODEX_PROXY_PROVIDER_LABEL", "OpenAI-Compatible").strip()
        or "OpenAI-Compatible",
        listen_host=env.get("CODEX_PROXY_LISTEN_HOST", "127.0.0.1").strip() or "127.0.0.1",
        listen_port=int(env.get("CODEX_PROXY_LISTEN_PORT", "8787")),
        debug_log=env.get("CODEX_PROXY_DEBUG_LOG", "").strip(),
        extra_headers=extra_headers,
        context_window=int(env.get("CODEX_PROXY_CONTEXT_WINDOW", "262144")),
        max_output_tokens=int(env.get("CODEX_PROXY_MAX_OUTPUT_TOKENS", "16384")),
    )


def _parse_extra_headers(env: Mapping[str, str]) -> dict[str, str]:
    extra_headers_raw = env.get("CODEX_PROXY_EXTRA_HEADERS", "").strip()
    return json.loads(extra_headers_raw) if extra_headers_raw else {}
