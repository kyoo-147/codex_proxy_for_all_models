import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from codex_proxy_for_all_models.catalog import build_model_catalog, resolve_requested_profile
from codex_proxy_for_all_models.config import ProxyConfig
from codex_proxy_for_all_models.pool_config import PoolConfig, ProfileConfig

class CatalogTests(unittest.TestCase):
    def test_pool_mode_exposes_three_curated_models(self):
        config = ProxyConfig(
            upstream_base_url="", upstream_api_key="", upstream_model="codex-balanced",
            provider_label="Codex Pool Router",
            pool_config=PoolConfig(mode="pool", profiles={
                "codex-fast": ProfileConfig("codex-fast", "Codex Fast", ["coding_fast"]),
                "codex-balanced": ProfileConfig("codex-balanced", "Codex Balanced", ["cheap_free"]),
                "codex-strong": ProfileConfig("codex-strong", "Codex Strong", ["coding_strong"]),
            }, pools={}, providers={}),
        )
        payload = build_model_catalog(config)
        names = [m["display_name"] for m in payload["models"]]
        self.assertEqual(names, ["Codex Fast", "Codex Balanced", "Codex Strong"])
        for m in payload["models"]:
            self.assertIn("slug", m)
            self.assertIn("supported_reasoning_levels", m)
            self.assertIn("context_window", m)
    def test_single_upstream_mode_exposes_one_model(self):
        config = ProxyConfig(
            upstream_base_url="https://example.com/v1", upstream_api_key="secret",
            upstream_model="qwen/qwen3-8b", provider_label="Ollama",
        )
        payload = build_model_catalog(config)
        self.assertEqual(len(payload["models"]), 1)
        self.assertEqual(payload["models"][0]["slug"], "qwen/qwen3-8b")
    def test_resolve_requested_profile_returns_profile_slug(self):
        self.assertEqual(resolve_requested_profile("codex-fast", None), "codex-fast")

    def test_resolve_requested_profile_returns_default_when_none(self):
        config = ProxyConfig(
            upstream_base_url="", upstream_api_key="", upstream_model="codex-strong",
            pool_config=PoolConfig(mode="pool", profiles={
                "codex-fast": ProfileConfig("codex-fast", "Codex Fast", ["coding_fast"]),
                "codex-balanced": ProfileConfig("codex-balanced", "Codex Balanced", ["cheap_free"]),
                "codex-strong": ProfileConfig("codex-strong", "Codex Strong", ["coding_strong"]),
            }, pools={}, providers={}),
        )
        self.assertEqual(resolve_requested_profile(None, config), "codex-balanced")

    def test_resolve_requested_profile_defaults_to_balanced(self):
        self.assertEqual(resolve_requested_profile(None, None), "codex-balanced")

if __name__ == "__main__":
    unittest.main()
