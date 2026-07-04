import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from codex_proxy_for_all_models.cli import main
from codex_proxy_for_all_models.config import load_config
from codex_proxy_for_all_models.pool_config import load_pool_config


class PoolConfigTests(unittest.TestCase):
    def write_toml(self, toml_text: str) -> str:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".toml") as handle:
            handle.write(toml_text)
            return handle.name

    def test_loads_profiles_and_candidates_from_toml_and_env(self):
        toml_text = """
mode = "pool"

[profiles.codex-fast]
visible_slug = "codex-fast"
display_name = "Codex Fast"
pool_order = ["cheap_free"]

[profiles.codex-balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free", "coding_fast"]

[profiles.codex-strong]
visible_slug = "codex-strong"
display_name = "Codex Strong"
pool_order = ["coding_fast"]

[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_FREE_KEY"

[providers.nvidia_paid]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_PAID_KEY"

[[pools.cheap_free.candidates]]
provider = "nvidia_free"
model = "z-ai/glm-5.2"
api_key_env = "NVIDIA_FREE_KEY"
capabilities = ["free", "tool_call"]

[[pools.coding_fast.candidates]]
provider = "nvidia_paid"
model = "qwen/qwen3-8b"
api_key_env = "NVIDIA_PAID_KEY"
capabilities = ["tool_call"]
"""
        path = self.write_toml(toml_text)

        env = {
            "CODEX_PROXY_CONFIG_PATH": path,
            "NVIDIA_FREE_KEY": "token-1",
            "NVIDIA_PAID_KEY": "token-2",
        }

        config = load_pool_config(env)

        self.assertIsNotNone(config)
        self.assertEqual(config.mode, "pool")
        self.assertIn("codex-balanced", config.profiles)
        self.assertEqual(config.profiles["codex-balanced"].visible_slug, "codex-balanced")
        self.assertEqual(config.providers["nvidia_free"].api_key, "token-1")
        self.assertEqual(config.pools["cheap_free"].candidates[0].model, "z-ai/glm-5.2")
        self.assertEqual(config.pools["cheap_free"].candidates[0].api_key_env, "NVIDIA_FREE_KEY")

    def test_returns_none_when_no_pool_config_path_is_set(self):
        self.assertIsNone(load_pool_config({}))

    def test_invalid_toml_raises_actionable_error(self):
        path = self.write_toml('mode = "pool"\nprofiles = [')

        with self.assertRaisesRegex(ValueError, "Invalid pool config"):
            load_pool_config({"CODEX_PROXY_CONFIG_PATH": path})

    def test_missing_provider_env_raises(self):
        path = self.write_toml(
            """
mode = "pool"

[profiles.codex-fast]
visible_slug = "codex-fast"
display_name = "Codex Fast"
pool_order = ["cheap_free"]

[profiles.codex-balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free"]

[profiles.codex-strong]
visible_slug = "codex-strong"
display_name = "Codex Strong"
pool_order = ["cheap_free"]

[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_FREE_KEY"

[[pools.cheap_free.candidates]]
provider = "nvidia_free"
model = "z-ai/glm-5.2"
api_key_env = "NVIDIA_FREE_KEY"
capabilities = ["free"]
"""
        )

        with self.assertRaisesRegex(ValueError, "Missing env var: NVIDIA_FREE_KEY"):
            load_pool_config({"CODEX_PROXY_CONFIG_PATH": path})

    def test_pool_candidate_provider_must_exist(self):
        path = self.write_toml(
            """
mode = "pool"

[profiles.codex-fast]
visible_slug = "codex-fast"
display_name = "Codex Fast"
pool_order = ["cheap_free"]

[profiles.codex-balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free"]

[profiles.codex-strong]
visible_slug = "codex-strong"
display_name = "Codex Strong"
pool_order = ["cheap_free"]

[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_FREE_KEY"

[[pools.cheap_free.candidates]]
provider = "missing_provider"
model = "z-ai/glm-5.2"
api_key_env = "NVIDIA_FREE_KEY"
capabilities = ["free"]
"""
        )

        with self.assertRaisesRegex(
            ValueError,
            "Unknown provider 'missing_provider' in pool 'cheap_free'",
        ):
            load_pool_config({"CODEX_PROXY_CONFIG_PATH": path, "NVIDIA_FREE_KEY": "token-1"})

    def test_profile_pool_order_must_reference_defined_pool(self):
        path = self.write_toml(
            """
mode = "pool"

[profiles.codex-fast]
visible_slug = "codex-fast"
display_name = "Codex Fast"
pool_order = ["missing_pool"]

[profiles.codex-balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free"]

[profiles.codex-strong]
visible_slug = "codex-strong"
display_name = "Codex Strong"
pool_order = ["cheap_free"]

[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_FREE_KEY"

[[pools.cheap_free.candidates]]
provider = "nvidia_free"
model = "z-ai/glm-5.2"
api_key_env = "NVIDIA_FREE_KEY"
capabilities = ["free"]
"""
        )

        with self.assertRaisesRegex(
            ValueError,
            "Profile 'codex-fast' references unknown pool 'missing_pool'",
        ):
            load_pool_config({"CODEX_PROXY_CONFIG_PATH": path, "NVIDIA_FREE_KEY": "token-1"})

    def test_curated_profile_set_is_required(self):
        path = self.write_toml(
            """
mode = "pool"

[profiles.codex-balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free"]

[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_FREE_KEY"

[[pools.cheap_free.candidates]]
provider = "nvidia_free"
model = "z-ai/glm-5.2"
api_key_env = "NVIDIA_FREE_KEY"
capabilities = ["free"]
"""
        )

        with self.assertRaisesRegex(
            ValueError,
            "Missing curated profiles: codex-fast, codex-strong",
        ):
            load_pool_config({"CODEX_PROXY_CONFIG_PATH": path, "NVIDIA_FREE_KEY": "token-1"})

    def test_curated_profile_set_must_be_exact(self):
        path = self.write_toml(
            """
mode = "pool"

[profiles.codex-fast]
visible_slug = "codex-fast"
display_name = "Codex Fast"
pool_order = ["cheap_free"]

[profiles.codex-balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free"]

[profiles.codex-strong]
visible_slug = "codex-strong"
display_name = "Codex Strong"
pool_order = ["cheap_free"]

[profiles.codex-extra]
visible_slug = "codex-extra"
display_name = "Codex Extra"
pool_order = ["cheap_free"]

[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_FREE_KEY"

[[pools.cheap_free.candidates]]
provider = "nvidia_free"
model = "z-ai/glm-5.2"
api_key_env = "NVIDIA_FREE_KEY"
capabilities = ["free"]
"""
        )

        with self.assertRaisesRegex(
            ValueError,
            "Curated profiles must be exactly: codex-fast, codex-balanced, codex-strong",
        ):
            load_pool_config({"CODEX_PROXY_CONFIG_PATH": path, "NVIDIA_FREE_KEY": "token-1"})

    def test_unused_provider_env_is_not_required(self):
        path = self.write_toml(
            """
mode = "pool"

[profiles.codex-fast]
visible_slug = "codex-fast"
display_name = "Codex Fast"
pool_order = ["cheap_free"]

[profiles.codex-balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free"]

[profiles.codex-strong]
visible_slug = "codex-strong"
display_name = "Codex Strong"
pool_order = ["cheap_free"]

[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_FREE_KEY"

[providers.nvidia_paid]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_PAID_KEY"

[[pools.cheap_free.candidates]]
provider = "nvidia_free"
model = "z-ai/glm-5.2"
api_key_env = "NVIDIA_FREE_KEY"
capabilities = ["free"]
"""
        )

        config = load_pool_config({"CODEX_PROXY_CONFIG_PATH": path, "NVIDIA_FREE_KEY": "token-1"})

        self.assertIsNotNone(config)
        self.assertEqual(config.providers["nvidia_free"].api_key, "token-1")
        self.assertEqual(config.providers["nvidia_paid"].api_key, "")

    def test_missing_pools_table_raises(self):
        path = self.write_toml(
            """
mode = "pool"

[profiles.codex-fast]
visible_slug = "codex-fast"
display_name = "Codex Fast"
pool_order = ["cheap_free"]

[profiles.codex-balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free"]

[profiles.codex-strong]
visible_slug = "codex-strong"
display_name = "Codex Strong"
pool_order = ["cheap_free"]

[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_FREE_KEY"
"""
        )

        with self.assertRaisesRegex(ValueError, "Pool config missing pools"):
            load_pool_config({"CODEX_PROXY_CONFIG_PATH": path, "NVIDIA_FREE_KEY": "token-1"})

    def test_missing_providers_table_raises(self):
        path = self.write_toml(
            """
mode = "pool"

[profiles.codex-fast]
visible_slug = "codex-fast"
display_name = "Codex Fast"
pool_order = ["cheap_free"]

[profiles.codex-balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free"]

[profiles.codex-strong]
visible_slug = "codex-strong"
display_name = "Codex Strong"
pool_order = ["cheap_free"]

[[pools.cheap_free.candidates]]
provider = "nvidia_free"
model = "z-ai/glm-5.2"
api_key_env = "NVIDIA_FREE_KEY"
capabilities = ["free"]
"""
        )

        with self.assertRaisesRegex(ValueError, "Pool config missing providers"):
            load_pool_config({"CODEX_PROXY_CONFIG_PATH": path, "NVIDIA_FREE_KEY": "token-1"})

    def test_example_pool_config_defines_exact_curated_profiles(self):
        env = {
            "CODEX_PROXY_CONFIG_PATH": str(ROOT / "config-examples" / "codex-pool.toml"),
            "NVIDIA_FREE_KEY": "token-1",
            "NVIDIA_PAID_KEY": "token-2",
        }

        config = load_pool_config(env)

        self.assertEqual(
            list(config.profiles.keys()),
            ["codex-fast", "codex-balanced", "codex-strong"],
        )

    def test_pool_mode_defaults_to_balanced_profile_slug(self):
        env = {
            "CODEX_PROXY_CONFIG_PATH": str(ROOT / "config-examples" / "codex-pool.toml"),
            "NVIDIA_FREE_KEY": "token-1",
            "NVIDIA_PAID_KEY": "token-2",
        }

        config = load_pool_config(env)

        self.assertEqual(config.default_visible_slug(), "codex-balanced")

    def test_pool_mode_derives_single_upstream_bridge_from_default_profile(self):
        env = {
            "CODEX_PROXY_CONFIG_PATH": str(ROOT / "config-examples" / "codex-pool.toml"),
            "NVIDIA_FREE_KEY": "token-1",
            "NVIDIA_PAID_KEY": "token-2",
        }

        config = load_config(env)

        self.assertEqual(config.upstream_base_url, "https://integrate.api.nvidia.com/v1")
        self.assertEqual(config.upstream_api_key, "token-1")
        self.assertEqual(config.upstream_model, "z-ai/glm-5.2")
        self.assertEqual(config.provider_label, "Codex Pool Router")

    def test_pool_mode_cli_prints_listen_and_profile_summary(self):
        pool_path = self.write_toml(
            """
mode = "pool"

[profiles.codex-fast]
visible_slug = "codex-fast"
display_name = "Codex Fast"
pool_order = ["cheap_free"]

[profiles.codex-balanced]
visible_slug = "codex-balanced"
display_name = "Codex Balanced"
pool_order = ["cheap_free", "coding_fast"]

[profiles.codex-strong]
visible_slug = "codex-strong"
display_name = "Codex Strong"
pool_order = ["coding_fast"]

[providers.nvidia_free]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_FREE_KEY"

[providers.nvidia_paid]
base_url = "https://integrate.api.nvidia.com/v1"
provider_label = "NVIDIA Build"
api_key_env = "NVIDIA_PAID_KEY"

[[pools.cheap_free.candidates]]
provider = "nvidia_free"
model = "z-ai/glm-5.2"
api_key_env = "NVIDIA_FREE_KEY"
capabilities = ["free"]

[[pools.coding_fast.candidates]]
provider = "nvidia_paid"
model = "qwen/qwen3-8b"
api_key_env = "NVIDIA_PAID_KEY"
capabilities = ["tool_call"]
"""
        )
        env = {
            "CODEX_PROXY_CONFIG_PATH": pool_path,
            "CODEX_PROXY_LISTEN_HOST": "127.0.0.1",
            "CODEX_PROXY_LISTEN_PORT": "8787",
            "NVIDIA_FREE_KEY": "token-1",
            "NVIDIA_PAID_KEY": "token-2",
        }
        stream = StringIO()

        from unittest.mock import patch

        with patch.dict("os.environ", env, clear=True):
            with patch("codex_proxy_for_all_models.cli.create_server") as create_server:
                create_server.return_value.serve_forever.side_effect = KeyboardInterrupt()
                with redirect_stdout(stream):
                    main()

        output = stream.getvalue()
        self.assertIn("[proxy] mode=pool", output)
        self.assertIn("Listen: http://127.0.0.1:8787", output)
        self.assertIn("Profiles: codex-fast, codex-balanced, codex-strong", output)
        self.assertIn("Default model: z-ai/glm-5.2", output)


if __name__ == "__main__":
    unittest.main()
