from __future__ import annotations

import json
import urllib.error
import urllib.request


def _post_chat_completion(base_url, api_key, extra_headers, payload):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "codex-proxy-for-all-models/0.2",
    }
    headers.update(extra_headers)
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Upstream {exc.code}: {body}") from exc


def classify_upstream_failure(error: Exception) -> str:
    msg = str(error)
    if "429" in msg:
        return "rate_limit"
    if msg.startswith("Upstream 5"):
        return "server_error"
    if "401" in msg or "403" in msg:
        return "auth"
    if "404" in msg or "not found" in msg.lower():
        return "not_found"
    if "timeout" in msg.lower():
        return "timeout"
    return "server_error"


def call_upstream(config, payload, requested_model, reasoning_effort):
    if config.pool_config is None:
        payload["model"] = config.bridge_upstream_model
        return _post_chat_completion(
            config.bridge_upstream_base_url,
            config.bridge_upstream_api_key,
            config.extra_headers or {},
            payload,
        )

    from .catalog import resolve_requested_profile

    profile_slug = resolve_requested_profile(requested_model, config)
    max_attempts = getattr(config.pool_config, "max_attempts", 3)
    attempts = []
    for _ in range(max_attempts):
        candidate = config.pool_router.select_candidate(profile_slug, reasoning_effort)
        payload["model"] = candidate.model
        try:
            resp = _post_chat_completion(
                candidate.base_url,
                candidate.api_key,
                config.extra_headers or {},
                payload,
            )
            config.pool_router.report_success(candidate.candidate_id)
            return resp
        except Exception as exc:
            failure = classify_upstream_failure(exc)
            config.pool_router.report_failure(candidate.candidate_id, failure)
            attempts.append(f"{candidate.model}:{failure}")
    raise RuntimeError(
        f"Pool request failed for {profile_slug}; attempts={', '.join(attempts)}"
    )
