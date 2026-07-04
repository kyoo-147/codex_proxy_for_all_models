import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from codex_proxy_for_all_models.router import PoolRouter, RoutedCandidate
from codex_proxy_for_all_models.pool_config import PoolConfig, ProfileConfig, ProviderConfig, CandidateConfig, PoolDefinition

class RouterTests(unittest.TestCase):
    def _make_config(self):
        return PoolConfig(
            mode="pool",
            profiles={
                "codex-fast": ProfileConfig("codex-fast", "Codex Fast", ["coding_fast"]),
                "codex-balanced": ProfileConfig("codex-balanced", "Codex Balanced", ["cheap_free", "coding_fast"]),
                "codex-strong": ProfileConfig("codex-strong", "Codex Strong", ["coding_strong"]),
            },
            providers={
                "nvidia_free": ProviderConfig("nvidia_free", "https://free.nvidia.com/v1", "NVIDIA Free", "NVIDIA_FREE_KEY", "key-free"),
                "nvidia_paid": ProviderConfig("nvidia_paid", "https://paid.nvidia.com/v1", "NVIDIA Paid", "NVIDIA_PAID_KEY", "key-paid"),
            },
            pools={
                "cheap_free": PoolDefinition(candidates=[CandidateConfig("nvidia_free", "z-ai/glm-5.2", "NVIDIA_FREE_KEY", ["free"])]),
                "coding_fast": PoolDefinition(candidates=[CandidateConfig("nvidia_paid", "qwen/qwen3-8b", "NVIDIA_PAID_KEY", ["tool_call"])]),
                "coding_strong": PoolDefinition(candidates=[CandidateConfig("nvidia_paid", "deepseek/deepseek-v4", "NVIDIA_PAID_KEY", ["tool_call", "long_context"])]),
            },
        )

    def test_selects_first_healthy_candidate(self):
        router = PoolRouter(self._make_config())
        c = router.select_candidate("codex-balanced", "medium")
        self.assertEqual(c.model, "z-ai/glm-5.2")
        self.assertEqual(c.provider_name, "nvidia_free")

    def test_rate_limit_moves_candidate_to_cooldown_and_selects_next(self):
        router = PoolRouter(self._make_config())
        first = router.select_candidate("codex-balanced", "medium")
        router.report_failure(first.candidate_id, "rate_limit")
        second = router.select_candidate("codex-balanced", "medium")
        self.assertNotEqual(first.candidate_id, second.candidate_id)
        self.assertEqual(second.model, "qwen/qwen3-8b")

    def test_all_candidates_down_raises(self):
        router = PoolRouter(self._make_config())
        c1 = router.select_candidate("codex-fast", "medium")
        router.report_failure(c1.candidate_id, "auth")
        with self.assertRaises(RuntimeError):
            router.select_candidate("codex-fast", "medium")

    def test_report_success_makes_candidate_sticky(self):
        router = PoolRouter(self._make_config(), clock=lambda: 1000)
        first = router.select_candidate("codex-balanced", "medium")
        router.report_success(first.candidate_id)
        second = router.select_candidate("codex-balanced", "medium")
        self.assertEqual(first.candidate_id, second.candidate_id)

    def test_sticky_winner_expires(self):
        clock = [0]
        def tick():
            clock[0] += 100
            return clock[0]
        router = PoolRouter(self._make_config(), clock=tick)
        first = router.select_candidate("codex-balanced", "medium")
        router.report_success(first.candidate_id)
        second = router.select_candidate("codex-balanced", "medium")
        self.assertEqual(first.candidate_id, second.candidate_id)
        clock[0] += 100
        third = router.select_candidate("codex-balanced", "medium")
        self.assertEqual(first.candidate_id, third.candidate_id)

if __name__ == "__main__":
    unittest.main()
