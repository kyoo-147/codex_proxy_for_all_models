import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


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

        self.assertIsNotNone(config)
        self.assertEqual(config.mode, "pool")
        self.assertIn("codex_balanced", config.profiles)
        self.assertEqual(config.profiles["codex_balanced"].visible_slug, "codex-balanced")
        self.assertEqual(config.providers["nvidia_free"].api_key, "token-1")
        self.assertEqual(config.pools["cheap_free"].candidates[0].model, "z-ai/glm-5.2")
        self.assertEqual(config.pools["cheap_free"].candidates[0].api_key_env, "NVIDIA_FREE_KEY")

    def test_returns_none_when_no_pool_config_path_is_set(self):
        self.assertIsNone(load_pool_config({}))


if __name__ == "__main__":
    unittest.main()
