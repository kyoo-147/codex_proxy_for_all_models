import json
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from codex_proxy_for_all_models.providers import (
    _post_chat_completion,
    call_upstream,
    classify_upstream_failure,
)
from codex_proxy_for_all_models.config import ProxyConfig


def free_port():
    temp = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = temp.server_address[1]
    temp.server_close()
    return port


class FakeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        body = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": f"got model {data['model']}"},
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args):
        return


class ClassifyTests(unittest.TestCase):
    def test_classifies_429_as_rate_limit(self):
        err = RuntimeError("Upstream 429: too many requests")
        self.assertEqual(classify_upstream_failure(err), "rate_limit")

    def test_classifies_503_as_server_error(self):
        err = RuntimeError("Upstream 503: service unavailable")
        self.assertEqual(classify_upstream_failure(err), "server_error")

    def test_classifies_401_as_auth(self):
        err = RuntimeError("Upstream 401: unauthorized")
        self.assertEqual(classify_upstream_failure(err), "auth")

    def test_classifies_404_as_not_found(self):
        err = RuntimeError("Upstream 404: not found")
        self.assertEqual(classify_upstream_failure(err), "not_found")

    def test_classifies_timeout_as_timeout(self):
        err = RuntimeError("Connection timeout")
        self.assertEqual(classify_upstream_failure(err), "timeout")


class CallUpstreamTests(unittest.TestCase):
    def setUp(self):
        port = free_port()
        self.server = HTTPServer(("127.0.0.1", port), FakeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{port}/v1"
        time.sleep(0.05)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_single_upstream_posts_and_returns(self):
        config = ProxyConfig(
            upstream_base_url=self.base_url,
            upstream_api_key="test-key",
            upstream_model="qwen/qwen3-8b",
            bridge_upstream_base_url=self.base_url,
            bridge_upstream_api_key="test-key",
            bridge_upstream_model="qwen/qwen3-8b",
        )
        resp = call_upstream(config, {"messages": [{"role": "user", "content": "hi"}]}, None, "medium")
        self.assertEqual(resp["choices"][0]["message"]["content"], "got model qwen/qwen3-8b")


if __name__ == "__main__":
    unittest.main()
