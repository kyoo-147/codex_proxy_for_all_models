import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from codex_proxy_for_all_models.config import load_config


class LoadConfigTests(unittest.TestCase):
    def test_loads_required_environment(self):
        env = {
            "CODEX_PROXY_UPSTREAM_BASE_URL": "https://example.com/v1",
            "CODEX_PROXY_UPSTREAM_API_KEY": "secret",
            "CODEX_PROXY_UPSTREAM_MODEL": "qwen/qwen3-8b",
        }

        config = load_config(env)

        self.assertEqual(config.upstream_base_url, "https://example.com/v1")
        self.assertEqual(config.upstream_api_key, "secret")
        self.assertEqual(config.upstream_model, "qwen/qwen3-8b")
        self.assertEqual(config.provider_label, "OpenAI-Compatible")
        self.assertEqual(config.listen_host, "127.0.0.1")
        self.assertEqual(config.listen_port, 8787)

    def test_provider_label_and_headers_are_optional(self):
        env = {
            "CODEX_PROXY_UPSTREAM_BASE_URL": "https://example.com/v1/",
            "CODEX_PROXY_UPSTREAM_API_KEY": "secret",
            "CODEX_PROXY_UPSTREAM_MODEL": "deepseek-v3",
            "CODEX_PROXY_PROVIDER_LABEL": "DeepSeek",
            "CODEX_PROXY_EXTRA_HEADERS": '{"HTTP-Referer":"https://repo.example","X-App":"codex"}',
        }

        config = load_config(env)

        self.assertEqual(config.upstream_base_url, "https://example.com/v1")
        self.assertEqual(config.provider_label, "DeepSeek")
        self.assertEqual(
            config.extra_headers,
            {"HTTP-Referer": "https://repo.example", "X-App": "codex"},
        )

    def test_missing_required_environment_raises(self):
        with self.assertRaises(ValueError):
            load_config({})


if __name__ == "__main__":
    unittest.main()
