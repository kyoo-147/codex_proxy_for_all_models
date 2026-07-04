from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ProxyConfig


DEFAULT_BALANCED_SLUG = "codex-balanced"

REASONING_LEVELS = [
    {"effort": "low", "description": "Fast responses with lighter reasoning"},
    {"effort": "medium", "description": "Balanced speed and reasoning depth"},
    {"effort": "high", "description": "Greater reasoning depth for harder tasks"},
]


def build_model_catalog(config):
    if config.pool_config is None:
        return _single_upstream_catalog(config)
    models = []
    for profile in config.pool_config.profiles.values():
        models.append(_curated_model_entry(profile, config.context_window, config.max_output_tokens))
    return {"object": "list", "models": models}


def resolve_requested_profile(requested_model, config):
    if requested_model and requested_model.startswith("codex-"):
        return requested_model
    if config and config.pool_config:
        return config.pool_config.default_visible_slug()
    return DEFAULT_BALANCED_SLUG


def _single_upstream_catalog(config):
    from .protocol import model_catalog_payload
    return model_catalog_payload(
        model_slug=config.upstream_model,
        display_name=config.upstream_model,
        provider_label=config.provider_label,
        context_window=config.context_window,
        max_output_tokens=config.max_output_tokens,
    )


def _curated_model_entry(profile, context_window, max_output_tokens):
    return {
        "slug": profile.visible_slug,
        "id": profile.visible_slug,
        "display_name": profile.display_name,
        "description": profile.display_name,
        "default_reasoning_level": "medium",
        "supported_reasoning_levels": REASONING_LEVELS,
        "shell_type": "shell_command",
        "visibility": "list",
        "supported_in_api": True,
        "priority": 1,
        "additional_speed_tiers": [],
        "service_tiers": [],
        "availability_nux": None,
        "upgrade": None,
        "base_instructions": "You are Codex, a coding agent based on GPT-5.",
        "supports_reasoning_summaries": False,
        "default_reasoning_summary": "none",
        "support_verbosity": False,
        "default_verbosity": None,
        "apply_patch_tool_type": "freeform",
        "web_search_tool_type": "text_and_image",
        "truncation_policy": {"mode": "tokens", "limit": 10000},
        "supports_parallel_tool_calls": True,
        "supports_image_detail_original": False,
        "context_window": context_window,
        "max_context_window": context_window,
        "effective_context_window_percent": 95,
        "experimental_supported_tools": [],
        "input_modalities": ["text"],
        "supports_search_tool": False,
        "use_responses_lite": False,
        "max_output_tokens": max_output_tokens,
    }
