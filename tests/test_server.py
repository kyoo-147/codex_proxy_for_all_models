import json
import sys
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from codex_proxy_for_all_models.config import ProxyConfig
from codex_proxy_for_all_models.server import create_server


def free_port():
    temp = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = temp.server_address[1]
    temp.server_close()
    return port


class FakeUpstreamHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        if payload["messages"][-1]["content"] == "tool":
            body = {
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {"name": "shell_command", "arguments": '{"command":"echo hi"}'},
                                }
                            ],
                        },
                    }
                ],
            }
        else:
            body = {
                "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "OK"},
                    }
                ],
            }

        encoded = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        return


class ServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        upstream_port = free_port()
        self.upstream = HTTPServer(("127.0.0.1", upstream_port), FakeUpstreamHandler)
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.upstream_thread.start()

        proxy_port = free_port()
        config = ProxyConfig(
            upstream_base_url=f"http://127.0.0.1:{upstream_port}/v1",
            upstream_api_key="secret",
            upstream_model="qwen/qwen3-8b",
            provider_label="Ollama",
            listen_host="127.0.0.1",
            listen_port=proxy_port,
            debug_log="",
            extra_headers={},
            context_window=262144,
            max_output_tokens=16384,
        )
        self.proxy = create_server(config)
        self.proxy_thread = threading.Thread(target=self.proxy.serve_forever, daemon=True)
        self.proxy_thread.start()
        self.base_url = f"http://127.0.0.1:{proxy_port}"
        time.sleep(0.05)

    def tearDown(self):
        if hasattr(self, "proxy"):
            self.proxy.shutdown()
            self.proxy.server_close()
        if hasattr(self, "upstream"):
            self.upstream.shutdown()
            self.upstream.server_close()

    def test_health_and_models(self):
        health = json.loads(urllib.request.urlopen(f"{self.base_url}/health").read())
        models = json.loads(urllib.request.urlopen(f"{self.base_url}/v1/models").read())

        self.assertEqual(health["status"], "ok")
        self.assertEqual(models["models"][0]["slug"], "qwen/qwen3-8b")

    def test_responses_round_trip_text(self):
        req = urllib.request.Request(
            f"{self.base_url}/v1/responses",
            data=json.dumps({"model": "qwen/qwen3-8b", "input": "hello"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        payload = json.loads(urllib.request.urlopen(req).read())

        self.assertEqual(payload["output"][0]["type"], "message")
        self.assertEqual(payload["output"][0]["content"][0]["text"], "OK")

    def test_responses_round_trip_tool_call(self):
        req = urllib.request.Request(
            f"{self.base_url}/v1/responses",
            data=json.dumps({"model": "qwen/qwen3-8b", "input": "tool"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        payload = json.loads(urllib.request.urlopen(req).read())

        self.assertEqual(payload["status"], "in_progress")
        self.assertEqual(payload["output"][0]["type"], "function_call")
        self.assertEqual(payload["output"][0]["name"], "shell_command")

    def test_tool_loop_full_round_trip(self):
        req = urllib.request.Request(
            f"{self.base_url}/v1/responses",
            data=json.dumps({
                "input": [
                    {"type": "function_call", "call_id": "call_1", "name": "shell_command", "arguments": '{"cmd":"echo hi"}'},
                    {"type": "function_call_output", "call_id": "call_1", "output": "hi"},
                ],
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        payload = json.loads(urllib.request.urlopen(req).read())

        self.assertEqual(payload["output"][0]["type"], "message")
        self.assertEqual(payload["output"][0]["content"][0]["text"], "OK")


class PoolModeServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        upstream_port = free_port()
        self.upstream_requests = []

        parent = self

        class PoolFakeUpstreamHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                parent.upstream_requests.append(
                    {
                        "path": self.path,
                        "authorization": self.headers.get("Authorization"),
                        "payload": payload,
                    }
                )
                body = {
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": "OK"},
                        }
                    ],
                }
                encoded = json.dumps(body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        self.upstream = HTTPServer(("127.0.0.1", upstream_port), PoolFakeUpstreamHandler)
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.upstream_thread.start()

        proxy_port = free_port()
        config = ProxyConfig(
            upstream_base_url=f"http://127.0.0.1:{upstream_port}/v1",
            upstream_api_key="provider-token",
            upstream_model="codex-balanced",
            bridge_upstream_base_url=f"http://127.0.0.1:{upstream_port}/v1",
            bridge_upstream_api_key="candidate-token",
            bridge_upstream_model="z-ai/glm-5.2",
            provider_label="Codex Pool Router",
            listen_host="127.0.0.1",
            listen_port=proxy_port,
            debug_log="",
            extra_headers={},
            context_window=262144,
            max_output_tokens=16384,
        )
        self.proxy = create_server(config)
        self.proxy_thread = threading.Thread(target=self.proxy.serve_forever, daemon=True)
        self.proxy_thread.start()
        self.base_url = f"http://127.0.0.1:{proxy_port}"
        time.sleep(0.05)

    def tearDown(self):
        self.proxy.shutdown()
        self.proxy.server_close()
        self.upstream.shutdown()
        self.upstream.server_close()

    def test_models_catalog_keeps_curated_slug(self):
        models = json.loads(urllib.request.urlopen(f"{self.base_url}/v1/models").read())

        self.assertEqual(models["models"][0]["slug"], "codex-balanced")
        self.assertEqual(models["models"][0]["display_name"], "codex-balanced")
        self.assertNotIn("z-ai/glm-5.2", json.dumps(models))

    def test_responses_keep_curated_model_and_use_bridge_credentials(self):
        req = urllib.request.Request(
            f"{self.base_url}/v1/responses",
            data=json.dumps({"model": "codex-balanced", "input": "hello"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        payload = json.loads(urllib.request.urlopen(req).read())

        self.assertEqual(payload["model"], "codex-balanced")
        self.assertEqual(self.upstream_requests[0]["authorization"], "Bearer candidate-token")
        self.assertEqual(self.upstream_requests[0]["payload"]["model"], "z-ai/glm-5.2")


class UpstreamErrorIntegrationTests(unittest.TestCase):
    @staticmethod
    def _make_error_handler(status_code: int):
        class ErrorFakeHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(length)
                body = json.dumps({"error": f"test {status_code}"}).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                return

        return ErrorFakeHandler

    def _setup(self, handler):
        upstream_port = free_port()
        self.upstream = HTTPServer(("127.0.0.1", upstream_port), handler)
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.upstream_thread.start()

        proxy_port = free_port()
        config = ProxyConfig(
            upstream_base_url=f"http://127.0.0.1:{upstream_port}/v1",
            upstream_api_key="secret",
            upstream_model="qwen/qwen3-8b",
            provider_label="Ollama",
            listen_host="127.0.0.1",
            listen_port=proxy_port,
        )
        self.proxy = create_server(config)
        self.proxy_thread = threading.Thread(target=self.proxy.serve_forever, daemon=True)
        self.proxy_thread.start()
        self.base_url = f"http://127.0.0.1:{proxy_port}"
        time.sleep(0.05)

    def tearDown(self):
        self.proxy.shutdown()
        self.proxy.server_close()
        self.upstream.shutdown()
        self.upstream.server_close()

    def _assert_error(self, expected_code: int, expected_type: str):
        req = urllib.request.Request(
            f"{self.base_url}/v1/responses",
            data=json.dumps({"input": "hello"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            self.fail("expected error")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, expected_code)
            body = json.loads(exc.read())
            self.assertEqual(body["error"]["type"], expected_type)

    def test_401_returns_authentication_error(self):
        self._setup(self._make_error_handler(401))
        self._assert_error(401, "authentication_error")

    def test_403_returns_authentication_error(self):
        self._setup(self._make_error_handler(403))
        self._assert_error(403, "authentication_error")

    def test_429_returns_rate_limit_error(self):
        self._setup(self._make_error_handler(429))
        self._assert_error(429, "rate_limit_error")

    def test_500_returns_upstream_error(self):
        self._setup(self._make_error_handler(500))
        self._assert_error(502, "upstream_error")

    def test_503_returns_upstream_error(self):
        self._setup(self._make_error_handler(503))
        self._assert_error(502, "upstream_error")

    def test_404_returns_not_found_error(self):
        self._setup(self._make_error_handler(404))
        self._assert_error(404, "not_found_error")


if __name__ == "__main__":
    unittest.main()
