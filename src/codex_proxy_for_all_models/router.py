import threading
import time
from dataclasses import dataclass

from .pool_config import PoolConfig


@dataclass(slots=True)
class RoutedCandidate:
    candidate_id: str
    provider_name: str
    model: str
    api_key: str
    base_url: str


_FAILURE_COOLDOWNS = {
    "rate_limit": 90,
    "server_error": 45,
    "timeout": 30,
    "auth": 3600,
    "not_found": 3600,
}

_STICKY_WINDOW = 30.0

# Reasoning effort → preferred pool name suffix mapping
_REASONING_POOL_MAP = {
    "low": "coding_fast",
    "medium": "cheap_free",
    "high": "coding_strong",
}


class PoolRouter:
    def __init__(self, config, clock=None):
        self._config = config
        self._clock = clock or time.time
        self._lock = threading.Lock()
        self._cooldowns = {}
        self._sticky_winners = {}

    def select_candidate(self, profile_slug, reasoning_effort):
        with self._lock:
            profile = self._config.profiles.get(profile_slug)
            if profile is None:
                raise RuntimeError(f"Unknown profile: {profile_slug}")

            pool_names = self._resolve_pool_order(profile.pool_order, reasoning_effort)
            now = self._clock()

            sticky = self._sticky_winners.get(profile_slug)
            if sticky and sticky[1] > now:
                try:
                    candidate = self._config.candidate_by_id(sticky[0])
                    cid = self._candidate_id(candidate)
                    if not self._is_in_cooldown(cid, now):
                        return self._to_routed(candidate)
                except KeyError:
                    pass

            for pool_name in pool_names:
                pool = self._config.pools.get(pool_name)
                if pool is None:
                    continue
                for candidate in pool.candidates:
                    cid = self._candidate_id(candidate)
                    if not self._is_in_cooldown(cid, now):
                        return self._to_routed(candidate)

            raise RuntimeError(f"All candidates unavailable for profile {profile_slug}")

    def _resolve_pool_order(self, base_order, reasoning_effort):
        if reasoning_effort not in _REASONING_POOL_MAP:
            return base_order

        preferred = _REASONING_POOL_MAP[reasoning_effort]
        if preferred in base_order:
            reordered = list(base_order)
            reordered.remove(preferred)
            reordered.insert(0, preferred)
            return reordered

        return base_order

    def report_success(self, candidate_id):
        now = self._clock()
        with self._lock:
            for slug in self._config.profiles:
                self._sticky_winners[slug] = (candidate_id, now + _STICKY_WINDOW)

    def report_failure(self, candidate_id, failure):
        delay = _FAILURE_COOLDOWNS.get(failure, 60)
        with self._lock:
            self._cooldowns[candidate_id] = self._clock() + delay

    def _is_in_cooldown(self, candidate_id, now):
        until = self._cooldowns.get(candidate_id, 0.0)
        return until > now

    def _candidate_id(self, candidate):
        return f"{candidate.provider}/{candidate.model}"

    def _to_routed(self, candidate):
        provider = self._config.providers.get(candidate.provider)
        if provider is None:
            raise RuntimeError(f"Unknown provider: {candidate.provider}")
        return RoutedCandidate(
            candidate_id=self._candidate_id(candidate),
            provider_name=candidate.provider,
            model=candidate.model,
            api_key=provider.api_key,
            base_url=provider.base_url,
        )
